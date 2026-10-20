from __future__ import annotations
import argparse
import asyncio
import json
import os
from pathlib import Path
from .models import Job, load_settings, load_profile
from .pipeline import Agent

def load_agent(config: Path) -> Agent:
    config=config.resolve()
    settings=load_settings(config)
    return Agent(settings,load_profile(config.parent/settings.profile),config.parent)

def main():
    parser=argparse.ArgumentParser(description="Campus job discovery to application packet")
    parser.add_argument("--config",type=Path,default=Path(os.getenv("CAMPUS_AGENT_CONFIG","config.example.json")))
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("status")
    demo=sub.add_parser("demo",help="Offline demo; never contacts Gemini, boards or SMTP")
    demo.add_argument("--output",type=Path,default=Path("demo"))
    scan=sub.add_parser("scan",help="Fetch configured sources once")
    scan.add_argument("--send",action="store_true",help="Deliver packets to configured MAIL_TO using SMTP")
    watch=sub.add_parser("watch",help="Run the 10-minute scheduler in the configured hours")
    watch.add_argument("--send",action="store_true")
    serve=sub.add_parser("serve",help="Local dashboard; scan button prepares files only")
    serve.add_argument("--port",type=int,default=8876)
    sub.add_parser("mcp",help="Start MCP stdio server; no email-sending tool")
    workspace=sub.add_parser("workspace",help="Real job workspace with connected Gmail and Google Drive")
    workspace.add_argument("--directory",type=Path,default=Path("workspace"))
    workspace.add_argument("--port",type=int,default=8877)
    morning=sub.add_parser("morning",help="Run the authorized daily job search and own-inbox packet delivery")
    morning.add_argument("--directory",type=Path,default=Path("workspace"))
    morning.add_argument("--port",type=int,default=8877)
    morning.add_argument("--extended",action="store_true")
    morning.add_argument("--session",choices=["morning","afternoon","standout"],default="morning")
    prepare=sub.add_parser("prepare",help="Rebuild one packet from its stored job ID")
    prepare.add_argument("job_id")
    resolve=sub.add_parser("resolve-delivery",help="Resolve a sending/needs_review state after checking the inbox")
    resolve.add_argument("job_id")
    resolve.add_argument("--result",choices=["sent","retry"],required=True)
    args=parser.parse_args()
    if args.command=="morning":
        from .morning import run_command
        result=run_command(args.directory,args.extended,args.port,args.session)
        print(json.dumps(result,indent=2,default=str))
        return
    if args.command=="workspace":
        from .workspace_web import serve_workspace
        serve_workspace(args.directory,args.port)
        return
    if args.command=="demo":
        config=args.config.resolve()
        settings=load_settings(config).model_copy(update={"offline":True,"database":"data/demo.db","artifacts":"artifacts","ai_provider":"local","first_run":"notify"})
        profile=load_profile(config.parent/settings.profile)
        base=args.output.resolve()
        agent=Agent(settings,profile,base)
        fixture=json.loads((config.parent/"examples/jobs.json").read_text(encoding="utf-8"))
        jobs=[Job.model_validate(x) for x in fixture]
        supplied={s.id:[j for j in jobs if j.source_id==s.id] for s in settings.sources}
        result=asyncio.run(agent.scan(supplied=supplied))
        # Write a self-contained demo config for dashboard and repeatable duplicate checks.
        demo_settings=settings.model_copy(update={"profile":str((config.parent/settings.profile).resolve())})
        (base/"config.json").write_text(demo_settings.model_dump_json(indent=2),encoding="utf-8")
        print(json.dumps(result,indent=2))
        print(f"\nPreview: python -m campus_agent --config \"{base/'config.json'}\" serve")
        return
    agent=load_agent(args.config)
    if args.command=="scan":
        report=asyncio.run(agent.scan(send=args.send))
        print(json.dumps(report,indent=2))
        if report["errors"]:
            raise SystemExit(1)
    elif args.command=="status":
        print(json.dumps(agent.status(),indent=2))
    elif args.command=="prepare":
        row=agent.store.get(args.job_id)
        if not row:
            parser.error("Unknown job ID")
        from .pipeline import process_lock
        with process_lock(agent.artifacts):
            if row["status"] in {"sending","needs_review","sent"}:
                parser.error("Resolve delivery before rebuilding a sent or ambiguous packet")
            print(agent.prepare(Job.model_validate_json(row["payload"])))
    elif args.command=="resolve-delivery":
        row=agent.store.get(args.job_id)
        if not row or row["status"] not in {"sending","needs_review"}:
            parser.error("Job must be in sending or needs_review")
        agent.store.update(args.job_id,"sent" if args.result=="sent" else "prepared",row["packet_dir"])
        print("Delivery state updated.")
    elif args.command=="serve":
        from .web import serve
        serve(agent,args.port)
    elif args.command=="mcp":
        from .mcp_server import make_server
        make_server(agent).run(transport="stdio")
    elif args.command=="watch":
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from .mail import check_mail_settings
        if args.send:
            check_mail_settings(agent.profile)
        scheduler=BlockingScheduler(timezone=agent.settings.timezone)
        def tick():
            if agent.settings.in_window():
                try:
                    print(json.dumps(asyncio.run(agent.scan(send=args.send))),flush=True)
                except Exception as exc:
                    print(json.dumps({"error":type(exc).__name__}),flush=True)
        scheduler.add_job(tick,IntervalTrigger(minutes=agent.settings.interval_minutes),
                          id="scan",max_instances=1,coalesce=True,misfire_grace_time=60)
        print("Scheduler active. Keep this process running. Ctrl+C to stop.",flush=True)
        tick()
        try:
            scheduler.start()
        except (KeyboardInterrupt,SystemExit):
            if scheduler.running:
                scheduler.shutdown(wait=True)

if __name__=="__main__":
    main()

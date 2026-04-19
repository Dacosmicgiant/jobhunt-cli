import logging
import typer
import webbrowser
from typing import Optional
from jobhunt.core.aggregator import aggregate
from jobhunt.core.formatter import print_jobs
from jobhunt.sources.indeed import IndeedSource
from jobhunt.sources.hirist import HiristSource
from jobhunt.sources.internshala import InternshalaSource
from jobhunt.utils.config import load_config, save_config, show_config
from jobhunt.utils.digest import filter_new, mark_seen, reset_seen
from jobhunt.utils.exporter import auto_save

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

app = typer.Typer(
    name="jobhunt",
    help="Aggregate fresher full-stack roles from multiple platforms.",
    add_completion=False,
)

config_app = typer.Typer(help="Manage jobhunt config (~/.jobhunt.toml)")
app.add_typer(config_app, name="config")

SOURCE_MAP = {
    "indeed":      IndeedSource(),
    "hirist":      HiristSource(),
    "internshala": InternshalaSource(),
}

BROWSER_PLATFORMS = {
    "linkedin":  "https://www.linkedin.com/jobs/search/?keywords={role}&location={location}&f_E=1",
    "cutshort":  "https://cutshort.io/jobs?role={role}",
    "wellfound": "https://wellfound.com/location/{location}?role={role}",
    "naukri":    "https://www.naukri.com/{role}-jobs?k={role}&l={location}",
}


def _build_query(role, location, experience, skills, limit) -> dict:
    fetch_limit = min(limit * 3, 150)
    return {
        "role":       role,
        "location":   location,
        "experience": experience,
        "skills":     skills,
        "limit":      fetch_limit,
    }


@app.command()
def search(
    role: Optional[str] = typer.Option(None, "--role", "-r"),
    location: Optional[str] = typer.Option(None, "--location", "-l"),
    experience: Optional[int] = typer.Option(None, "--experience", "-e"),
    skills: Optional[str] = typer.Option(None, "--skills", "-s",
        help="Comma-separated skills, e.g. react,node,mongodb"),
    platforms: Optional[str] = typer.Option(None, "--platforms", "-p",
        help="Comma-separated platforms"),
    limit: Optional[int] = typer.Option(None, "--limit"),
    save_defaults: bool = typer.Option(False, "--save-defaults",
        help="Save these flags as new defaults in ~/.jobhunt.toml"),
    digest: bool = typer.Option(False, "--digest", "-d",
        help="Show only new jobs since last run"),
    save: Optional[str] = typer.Option(None, "--save",
        help="Export results: json or csv"),
):
    """Search for fresher full-stack jobs."""
    cfg = load_config()

    _role       = role       or cfg["role"]
    _location   = location   or cfg["location"]
    _experience = experience if experience is not None else cfg["experience"]
    _skills_str = skills     or ",".join(cfg["skills"])
    _platforms  = platforms  or ",".join(cfg["platforms"])
    _limit      = limit      or cfg["limit"]
    _skills     = [s.strip() for s in _skills_str.split(",") if s.strip()]

    if save_defaults:
        save_config({
            "role":       _role,
            "location":   _location,
            "experience": _experience,
            "skills":     _skills,
            "platforms":  _platforms.split(","),
            "limit":      _limit,
        })
        typer.echo("✅ Saved defaults to ~/.jobhunt.toml")

    query    = _build_query(_role, _location, _experience, _skills, _limit)
    selected = [SOURCE_MAP[p] for p in _platforms.split(",") if p in SOURCE_MAP]
    skipped  = [p for p in _platforms.split(",") if p not in SOURCE_MAP]

    if skipped:
        typer.echo(f"⚠  Skipping unknown/unimplemented platforms: {', '.join(skipped)}")
    if not selected:
        typer.echo("No valid platforms selected. Available: " + ", ".join(SOURCE_MAP))
        raise typer.Exit(1)

    jobs = aggregate(selected, query)

    if digest:
        jobs, total_seen = filter_new(jobs)
        typer.echo(f"🔍 Digest mode: {len(jobs)} new jobs (skipped {total_seen} already seen)")
        mark_seen(jobs)

    print_jobs(jobs, limit=_limit)

    if save:
        fmt = save.lower().strip()
        if fmt not in ("json", "csv"):
            typer.echo("⚠  --save must be 'json' or 'csv'")
        else:
            path = auto_save(jobs[:_limit], fmt)
            typer.echo(f"💾 Saved {min(len(jobs), _limit)} jobs to {path}")


@app.command()
def digest(
    reset: bool = typer.Option(False, "--reset", help="Clear seen jobs history"),
):
    """Show only new jobs since last run using saved config defaults."""
    if reset:
        reset_seen()
        typer.echo("✅ Seen jobs history cleared.")
        return

    cfg = load_config()
    typer.echo(f"🔍 Running digest — role: {cfg['role']} | platforms: {', '.join(cfg['platforms'])}")

    query    = _build_query(cfg["role"], cfg["location"], cfg["experience"], cfg["skills"], cfg["limit"])
    selected = [SOURCE_MAP[p] for p in cfg["platforms"] if p in SOURCE_MAP]

    if not selected:
        typer.echo("No valid platforms in config. Run: jobhunt config set --platforms indeed,hirist,internshala")
        raise typer.Exit(1)

    jobs                 = aggregate(selected, query)
    new_jobs, total_seen = filter_new(jobs)
    mark_seen(new_jobs)

    typer.echo(f"🔍 {len(new_jobs)} new jobs (skipped {total_seen} already seen)")
    print_jobs(new_jobs, limit=cfg["limit"])


@app.command()
def update(
    platforms: Optional[str] = typer.Option(None, "--platforms", "-p",
        help="Platforms to update. Defaults to all configured platforms."),
    force: bool = typer.Option(False, "--force",
        help="Force refresh even if cache is still fresh"),
):
    """Refresh job cache for expired or missing sources."""
    from jobhunt.utils.cache import cache_status, invalidate

    cfg        = load_config()
    _platforms = platforms or ",".join(cfg["platforms"])
    selected   = [p.strip() for p in _platforms.split(",") if p.strip() in SOURCE_MAP]

    if not selected:
        typer.echo("No valid platforms. Available: " + ", ".join(SOURCE_MAP))
        raise typer.Exit(1)

    query = _build_query(cfg["role"], cfg["location"], cfg["experience"], cfg["skills"], cfg["limit"])

    typer.echo(f"🔄 Checking cache for: {', '.join(selected)}\n")

    to_refresh = []
    for name in selected:
        status  = cache_status(name, query)
        age_str = f"{status['age_seconds']}s old" if status["age_seconds"] is not None else "not cached"
        expires = f", expires in {status['expires_in']}s" if status["expires_in"] is not None else ""
        icon    = "✅" if status["status"] == "fresh" else "⚠️ "
        typer.echo(f"  {icon} {name}: {status['status']} ({age_str}{expires})")
        if status["status"] != "fresh" or force:
            to_refresh.append(name)

    if not to_refresh:
        typer.echo("\n✅ All caches are fresh. Use --force to refresh anyway.")
        return

    typer.echo(f"\n🔄 Refreshing: {', '.join(to_refresh)}\n")

    for name in to_refresh:
        invalidate(name, query)
        source = SOURCE_MAP[name]
        try:
            jobs = source.search(query)
            typer.echo(f"  ✅ {name}: {len(jobs)} jobs cached")
        except Exception as e:
            typer.echo(f"  ❌ {name}: failed — {e}")

    typer.echo("\n✅ Update complete. Run 'jobhunt search' to see results.")


@app.command()
def open(
    platform: str = typer.Argument(..., help="Platform: linkedin | cutshort | wellfound | naukri"),
    role: Optional[str] = typer.Option(None, "--role", "-r"),
    location: Optional[str] = typer.Option(None, "--location", "-l"),
):
    """Open a browser-only platform with a pre-filtered search URL."""
    cfg       = load_config()
    _role     = role     or cfg["role"]
    _location = location or cfg["location"]

    template = BROWSER_PLATFORMS.get(platform.lower())
    if not template:
        typer.echo(f"Unknown platform '{platform}'. Supported: {', '.join(BROWSER_PLATFORMS)}")
        raise typer.Exit(1)

    url = template.format(
        role=_role.replace(" ", "+"),
        location=_location.replace(" ", "+")
    )
    typer.echo(f"Opening {platform}: {url}")
    webbrowser.open(url)


# --- Config subcommands ---

@config_app.command("show")
def config_show():
    """Show current config (~/.jobhunt.toml)."""
    show_config()


@config_app.command("set")
def config_set(
    role: Optional[str] = typer.Option(None, "--role", "-r"),
    location: Optional[str] = typer.Option(None, "--location", "-l"),
    experience: Optional[int] = typer.Option(None, "--experience", "-e"),
    skills: Optional[str] = typer.Option(None, "--skills", "-s"),
    platforms: Optional[str] = typer.Option(None, "--platforms", "-p"),
    limit: Optional[int] = typer.Option(None, "--limit"),
):
    """Set one or more config defaults."""
    cfg = load_config()
    if role:                   cfg["role"] = role
    if location:               cfg["location"] = location
    if experience is not None: cfg["experience"] = experience
    if skills:                 cfg["skills"] = [s.strip() for s in skills.split(",") if s.strip()]
    if platforms:              cfg["platforms"] = [p.strip() for p in platforms.split(",") if p.strip()]
    if limit:                  cfg["limit"] = limit
    save_config(cfg)
    typer.echo("✅ Config updated:")
    show_config()


@config_app.command("reset")
def config_reset():
    """Reset config to factory defaults."""
    from jobhunt.utils.config import CONFIG_PATH
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
    typer.echo("✅ Config reset to defaults.")
    show_config()


if __name__ == "__main__":
    app()
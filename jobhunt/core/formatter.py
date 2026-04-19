from rich.console import Console
from rich.table import Table
from rich import box
from jobhunt.models.job import Job
console = Console()


def _score_color(score: float | None) -> str:
    if score is None:
        return "dim"
    if score >= 0.75:
        return "bold green"
    if score >= 0.55:
        return "yellow"
    return "dim red"


def print_jobs(jobs: list[Job], limit: int = 30) -> None:
    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    table = Table(
        title=f"[bold green]jobhunt[/bold green] — {len(jobs[:limit])} results",
        box=box.ROUNDED,
        show_lines=True,
        highlight=True,
    )

    table.add_column("Score",   style="bold",      width=6)
    table.add_column("#",       style="dim",        width=3)
    table.add_column("Title",   style="bold cyan",  max_width=28)
    table.add_column("Company", style="white",      max_width=18)
    table.add_column("Location",style="green",      max_width=14)
    table.add_column("Salary",  style="yellow",     max_width=16)
    table.add_column("Type",    style="magenta",    max_width=10)
    table.add_column("Posted",  style="yellow",     width=8)
    table.add_column("Skills",  style="dim cyan",   max_width=28)
    table.add_column("Snippet", style="dim",        max_width=35)
    table.add_column("Source",  style="magenta",    width=8)
    table.add_column("Link",    style="blue",       max_width=30)

    for i, job in enumerate(jobs[:limit], 1):
        score    = job.score or 0
        color    = _score_color(job.score)
        posted   = job.posted_at.strftime("%b %d") if job.posted_at else "—"
        skills   = ", ".join(job.skills[:3]) if job.skills else "—"
        snippet  = job.snippet[:80] + "…" if job.snippet and len(job.snippet) > 80 else job.snippet or "—"
        benefits = ", ".join(job.benefits[:2]) if job.benefits else ""

        table.add_row(
            f"[{color}]{score:.2f}[/{color}]",
            str(i),
            job.title,
            job.company,
            job.location,
            job.salary or "—",
            job.job_type or "—",
            posted,
            skills,
            snippet,
            job.source,
            job.apply_url,
        )

    console.print(table)
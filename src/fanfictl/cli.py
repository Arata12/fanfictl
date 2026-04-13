from __future__ import annotations

import json
from pathlib import Path

import typer

from fanfictl.config import Settings
from fanfictl.exporters import (
    build_combined_markdown,
    write_epub,
    write_html,
    write_markdown,
    write_text,
)
from fanfictl.models import Checkpoint, ExportFormat, WorkKind
from fanfictl.pixiv import PixivClient, parse_pixiv_url
from fanfictl.storage import (
    ensure_work_dirs,
    load_checkpoint,
    save_checkpoint,
    save_metadata,
)
from fanfictl.translate import GeminiStudioProvider, translate_work


app = typer.Typer(help="Translate public Pixiv fanfiction into English")


@app.command()
def info(url: str) -> None:
    parsed = parse_pixiv_url(url)
    client = PixivClient()
    try:
        work = (
            client.fetch_novel_work(parsed.pixiv_id, parsed.url)
            if parsed.kind == "novel"
            else client.fetch_series_work(parsed.pixiv_id, parsed.url)
        )
    finally:
        client.close()

    typer.echo(
        json.dumps(
            {
                "kind": work.kind.value,
                "pixiv_id": work.pixiv_id,
                "title": work.original_title,
                "author": work.author_name,
                "chapters": len(work.chapters),
                "language": work.original_language,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command()
def translate(
    url: str,
    target: str = typer.Option("en", help="Target language code"),
    output: Path | None = typer.Option(None, help="Output directory"),
    format: list[ExportFormat] = typer.Option(
        [ExportFormat.MD, ExportFormat.TXT, ExportFormat.HTML, ExportFormat.EPUB],
        "--format",
        help="Export format(s)",
    ),
    resume: bool = typer.Option(False, help="Resume from checkpoint if present"),
    chapter_limit: int | None = typer.Option(
        None, help="Limit number of chapters for testing"
    ),
    model: str | None = typer.Option(None, help="Override model name"),
) -> None:
    if target.lower() != "en":
        raise typer.BadParameter("v1 only supports English output")

    settings = Settings()
    if not settings.gemini_api_key:
        typer.secho(
            "GEMINI_API_KEY is required for translation. Put it in .env or your shell environment.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    provider = GeminiStudioProvider(
        api_key=settings.gemini_api_key,
        model_name=model or settings.gemini_model,
    )

    parsed = parse_pixiv_url(url)
    client = PixivClient()
    try:
        work = (
            client.fetch_novel_work(parsed.pixiv_id, parsed.url)
            if parsed.kind == "novel"
            else client.fetch_series_work(parsed.pixiv_id, parsed.url)
        )
    finally:
        client.close()

    if chapter_limit:
        work.chapters = work.chapters[:chapter_limit]

    output_base = (output or settings.output_dir).resolve()
    work_root = ensure_work_dirs(output_base, work)
    checkpoint = load_checkpoint(work_root) if resume else None
    if checkpoint is None:
        checkpoint = Checkpoint(
            source_url=work.source_url,
            kind=work.kind,
            pixiv_id=work.pixiv_id,
            original_title=work.original_title,
            model_name=model or settings.gemini_model,
        )

    typer.echo(f"Translating {work.kind.value} {work.pixiv_id}: {work.original_title}")
    work = translate_work(
        work,
        provider,
        checkpoint,
        checkpoint_callback=lambda cp: save_checkpoint(work_root, cp),
    )
    save_checkpoint(work_root, checkpoint)
    save_metadata(work_root, work)

    for chapter in work.chapters:
        chapter_root = work_root / "chapters"
        (chapter_root / f"{chapter.position:03d}-source.md").write_text(
            chapter.source_markdown, encoding="utf-8"
        )
        if chapter.translated_markdown:
            (chapter_root / f"{chapter.position:03d}-translated.md").write_text(
                chapter.translated_markdown,
                encoding="utf-8",
            )

    combined_markdown = build_combined_markdown(work)
    title = work.translated_title or work.original_title
    if ExportFormat.MD in format:
        write_markdown(
            work_root
            / ("translated.md" if work.kind == WorkKind.NOVEL else "combined.md"),
            combined_markdown,
        )
    if ExportFormat.TXT in format:
        write_text(
            work_root
            / ("translated.txt" if work.kind == WorkKind.NOVEL else "combined.txt"),
            combined_markdown,
        )
    if ExportFormat.HTML in format:
        write_html(
            work_root
            / ("translated.html" if work.kind == WorkKind.NOVEL else "combined.html"),
            combined_markdown,
            title,
        )
    if ExportFormat.EPUB in format:
        write_epub(
            work_root
            / ("translated.epub" if work.kind == WorkKind.NOVEL else "combined.epub"),
            work,
        )

    typer.echo(f"Done: {work_root}")


if __name__ == "__main__":
    app()

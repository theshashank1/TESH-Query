"""
CLI Commands for managing the local GGUF LLM backend in TESH-Query.

Provides commands to inspect hardware acceleration, local model status,
and run smoke tests against local GGUF weights.
"""

import json
import os
import time
from typing import Optional
import typer
from rich.panel import Panel

from teshq.cli.ui import error, handle_error, print_header, status, success, tip, warning
from teshq.cli.ui.theme import Colors, Icons, ROUNDED_BOX, console
from teshq.config.loader import get_settings
from teshq.core.hardware import detect_hardware
from teshq.core.inference import InferenceConfig, InferenceRuntime
from teshq.core.model_manager import ModelManager

app = typer.Typer(
    name="local",
    help="Manage local GGUF models, hardware acceleration, and offline inference.",
    invoke_without_command=True,
)

PANEL_OUTPUT = "📊 Output Options"
PANEL_INFERENCE = "⚡ Inference Parameters"


@app.callback(invoke_without_command=True)
def local_default(ctx: typer.Context):
    """Default handler: Display local backend status and hardware profile."""
    if ctx.invoked_subcommand is None:
        local_status(as_json=False)


@app.command(name="status")
def local_status(
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output hardware detection and local backend status in JSON format.",
        rich_help_panel=PANEL_OUTPUT,
    ),
):
    """
    Check the status of the local backend, including hardware support and installed models.
    """
    try:
        # 1. Check if llama-cpp-python is installed
        try:
            import llama_cpp
            llama_installed = True
        except ImportError:
            llama_installed = False

        hw = detect_hardware()
        s = get_settings()

        model_path = s.local_model_path or ""
        model_exists = os.path.exists(model_path) if model_path else False
        model_size_gb = (os.path.getsize(model_path) / (1024 ** 3)) if model_exists else 0.0

        installed_models = ModelManager().get_installed_models()

        if as_json:
            result = {
                "llama_installed": llama_installed,
                "hardware": {
                    "cpu_cores": hw.cpu_cores,
                    "ram_total_gb": hw.ram_total_gb,
                    "ram_available_gb": hw.ram_available_gb,
                    "gpu_name": hw.gpu_name,
                    "gpu_vram_mb": hw.gpu_vram_mb,
                    "gpu_backend": hw.gpu_backend,
                    "recommended_quant": hw.recommended_quant,
                    "recommended_gpu_layers": hw.recommended_n_gpu_layers,
                    "recommended_ctx": hw.recommended_n_ctx,
                },
                "configured_model": {
                    "path": model_path,
                    "exists": model_exists,
                    "size_gb": round(model_size_gb, 2),
                },
                "installed_models_count": len(installed_models),
            }
            print(json.dumps(result, indent=2))
            raise typer.Exit(0)

        print_header("Local LLM Backend Status", level=2)

        # Backend Engine Status
        if llama_installed:
            backend_badge = f"[bold {Colors.SUCCESS}]{Icons.check()} Installed & Available[/bold {Colors.SUCCESS}]"
        else:
            backend_badge = f"[bold {Colors.WARNING}]{Icons.warn()} Not Installed (run: pip install teshq[local])[/bold {Colors.WARNING}]"

        # Model Status
        if model_exists:
            model_badge = (
                f"[bold {Colors.SUCCESS}]{Icons.check()} {os.path.basename(model_path)}[/bold {Colors.SUCCESS}] "
                f"[dim]({model_size_gb:.2f} GB)[/dim]"
            )
        elif model_path:
            model_badge = f"[bold {Colors.ERROR}]{Icons.cross()} File Missing: {model_path}[/bold {Colors.ERROR}]"
        elif installed_models:
            first_m = installed_models[0]
            model_badge = (
                f"[bold {Colors.WARNING}]Unconfigured[/bold {Colors.WARNING}] "
                f"[dim](Found downloaded: {first_m['filename']})[/dim]"
            )
        else:
            model_badge = f"[{Colors.TEXT_MUTED}]No local model installed or configured[/{Colors.TEXT_MUTED}]"

        gpu_desc = (
            f"{hw.gpu_name} ({hw.gpu_vram_mb} MB VRAM, {hw.gpu_backend.upper()})"
            if hw.gpu_name
            else "CPU Only (No dedicated GPU detected)"
        )

        status_text = f"""[{Colors.TEXT_TERTIARY}]Engine (llama-cpp):[/{Colors.TEXT_TERTIARY}] {backend_badge}
[{Colors.TEXT_TERTIARY}]Active Local Model:[/{Colors.TEXT_TERTIARY}] {model_badge}

[{Colors.TEXT_TERTIARY}]Host Hardware:[/{Colors.TEXT_TERTIARY}]
  • CPU:             [bold {Colors.TEXT_PRIMARY}]{hw.cpu_cores} Cores[/bold {Colors.TEXT_PRIMARY}]
  • Memory:          [bold {Colors.TEXT_PRIMARY}]{hw.ram_total_gb:.1f} GB Total[/bold {Colors.TEXT_PRIMARY}] [dim]({hw.ram_available_gb:.1f} GB available)[/dim]
  • Acceleration:    [bold {Colors.AI_ACCENT}]{gpu_desc}[/bold {Colors.AI_ACCENT}]

[{Colors.TEXT_TERTIARY}]Hardware Recommendations:[/{Colors.TEXT_TERTIARY}]
  • Recommended Model: [bold {Colors.PRIMARY}]Sub-4B parameters (e.g. Qwen 1.5B/3B)[/bold {Colors.PRIMARY}]
  • Quantization:      [bold {Colors.TEXT_SECONDARY}]{hw.recommended_quant}[/bold {Colors.TEXT_SECONDARY}]
  • Context Budget:    [bold {Colors.TEXT_SECONDARY}]{hw.recommended_n_ctx} tokens[/bold {Colors.TEXT_SECONDARY}]
  • GPU Layer Offload: [bold {Colors.TEXT_SECONDARY}]{hw.recommended_n_gpu_layers} layers[/bold {Colors.TEXT_SECONDARY}]"""

        console.print(
            Panel(
                status_text,
                title=f"[bold {Colors.PRIMARY}]{Icons.brain()} Local Inference Engine HUD[/bold {Colors.PRIMARY}]",
                box=ROUNDED_BOX,
                border_style=Colors.BORDER_DEFAULT,
                expand=False,
            )
        )

        if not llama_installed:
            tip("To enable local GGUF models on this system:")
            console.print(f"  [bold {Colors.PRIMARY}]pip install teshq[local][/bold {Colors.PRIMARY}]\n")
        elif not model_exists and installed_models:
            first_m = installed_models[0]
            tip(f"To configure your downloaded {first_m['filename']} model:")
            console.print(
                f"  [bold {Colors.PRIMARY}]teshq config --llm-provider local --local-model-path \"{first_m['path']}\"[/bold {Colors.PRIMARY}]\n"
            )

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print(f"\n[{Colors.TEXT_MUTED}]Operation cancelled.[/{Colors.TEXT_MUTED}]")
        raise typer.Exit(0)
    except Exception as e:
        handle_error(e, "Local Backend Status", suggest_action="Check hardware dependencies with 'teshq health'")
        raise typer.Exit(1)


@app.command(name="test")
def local_test(
    prompt: str = typer.Option(
        "Select 1 as test_val;",
        "--prompt",
        "-p",
        help="Prompt to run against the model.",
        rich_help_panel=PANEL_INFERENCE,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Display verbose token generation metrics.",
        rich_help_panel=PANEL_INFERENCE,
    ),
):
    """
    Perform a smoke test of the local GGUF runtime to verify speed and hardware acceleration.
    """
    print_header("Local Backend Smoke Test", level=2)

    try:
        import llama_cpp
    except ImportError:
        error("llama-cpp-python is not installed. Run: pip install teshq[local]")
        raise typer.Exit(1)

    s = get_settings()
    model_path = s.local_model_path if s.local_model_path else ""

    runtime = InferenceRuntime()
    config = InferenceConfig(
        model_path=model_path,
        n_ctx=s.local_n_ctx,
        n_gpu_layers=s.local_n_gpu_layers,
        n_threads=s.local_n_threads,
        verbose=verbose,
    )

    try:
        with status("Loading model in-process...", success_message="Model loaded successfully."):
            runtime.load(config)

        with status("Running generation for test prompt...", success_message="Generation finished."):
            result = runtime.generate(
                prompt=prompt,
                max_tokens=64,
                temperature=0.0,
            )

        console.print(f"\n[bold {Colors.TEXT_PRIMARY}]Prompt:[/bold {Colors.TEXT_PRIMARY}] {prompt}")
        console.print(f"[bold {Colors.SUCCESS}]Generated Output:[/bold {Colors.SUCCESS}] {result.text}\n")

        latency_str = f"{result.latency_ms:.2f} ms"
        tok_per_sec = (result.completion_tokens / result.latency_ms) * 1000 if result.latency_ms > 0 else 0.0

        metrics_text = (
            f"Latency: {latency_str} | Generated: {result.completion_tokens} tokens | "
            f"Speed: {tok_per_sec:.2f} tok/s"
        )
        tip(metrics_text)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print(f"\n[{Colors.TEXT_MUTED}]Smoke test cancelled.[/{Colors.TEXT_MUTED}]")
        raise typer.Exit(0)
    except Exception as e:
        error(f"Test failed with error: {e}")
        raise typer.Exit(1)
    finally:
        runtime.unload()


if __name__ == "__main__":
    app()

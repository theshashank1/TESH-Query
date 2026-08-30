"""
CLI Command for interactive chat using the local GGUF LLM backend in TESH-Query.
"""

import sys
import typer
from typing import List, Dict
from teshq.cli.ui import print_header, print_footer, error, warning, tip
from teshq.config.loader import get_settings
from teshq.core.inference import InferenceRuntime, InferenceConfig

app = typer.Typer(help="Interactive conversational interface for local GGUF models.")

@app.command(name="repl")
def chat_repl(
    system_prompt: str = typer.Option(
        "You are TESHQ Chat, a helpful database assistant. You can write SQL queries and answer general database questions.",
        "--system", "-s",
        help="System instructions for the assistant."
    ),
):
    """
    Start an interactive SQL and database chat session in your terminal.
    """
    print_header("TESHQ CHAT ASSISTANT", level=1)
    
    # 1. Verify model is configured and exists
    s = get_settings()
    if not s.local_model_path:
        error("LOCAL_MODEL_PATH is not configured in settings.")
        tip("Run: teshq config --local")
        raise typer.Exit(1)
        
    import os
    if not os.path.exists(s.local_model_path):
        error(f"GGUF model file not found at: '{s.local_model_path}'")
        tip("Run: teshq model pull")
        raise typer.Exit(1)

    # 2. Load the model
    runtime = InferenceRuntime()
    config = InferenceConfig(
        model_path=s.local_model_path,
        n_ctx=s.local_n_ctx,
        n_gpu_layers=s.local_n_gpu_layers,
        n_threads=s.local_n_threads,
        verbose=False
    )
    
    try:
        typer.secho("🤖 Loading local model into memory... (please wait)", fg="cyan")
        runtime.load(config)
        typer.secho("✅ Model loaded! Chat session active.", fg="green")
        typer.secho("Type 'exit' or 'quit' to end session. Type 'clear' to reset history.", dim=True)
        typer.echo("")
        
        history: List[Dict[str, str]] = []
        
        while True:
            try:
                # Prompt user for input
                user_input = typer.prompt("You")
                
                # Check control commands
                if user_input.lower().strip() in ("exit", "quit"):
                    typer.secho("Goodbye!", fg="cyan")
                    break
                    
                if user_input.lower().strip() == "clear":
                    history.clear()
                    typer.secho("🧹 Chat history cleared.", fg="magenta")
                    typer.echo("")
                    continue
                
                # Print assistant prefix
                typer.secho("Assistant: ", fg="green", bold=True, nl=False)
                
                # Build custom chat context with history
                prompt = ""
                for msg in history:
                    prompt += f"{msg['role'].capitalize()}: {msg['content']}\n"
                prompt += f"User: {user_input}\nAssistant:"
                
                # Stream the generation
                generated_text = ""
                for chunk in runtime.generate_stream(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=512,
                    temperature=0.7
                ):
                    typer.echo(chunk, nl=False)
                    sys.stdout.flush()
                    generated_text += chunk
                    
                typer.echo("")
                typer.echo("")
                
                # Save to history
                history.append({"role": "user", "content": user_input})
                history.append({"role": "assistant", "content": generated_text})
                
            except KeyboardInterrupt:
                typer.echo("")
                warning("Use 'exit' or 'quit' to close the session.")
                typer.echo("")
                continue
                
    except Exception as e:
        error(f"Chat session failed: {e}")
    finally:
        # Guarantee resources are freed on exit
        runtime.unload()
        
    print_footer("Session ended.")

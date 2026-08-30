"""
CLI Commands for managing the local GGUF LLM backend in TESH-Query.
"""

import time
import typer
from teshq.cli.ui import print_header, print_footer, status, error, warning, tip
from teshq.config.loader import get_llm_config, get_settings
from teshq.core.hardware import detect_hardware
from teshq.core.inference import InferenceRuntime, InferenceConfig

app = typer.Typer(help="Manage local GGUF models and hardware configurations.")

@app.command(name="status")
def local_status():
    """
    Check the status of the local backend, including hardware support and installed models.
    """
    print_header("Local LLM Backend Status", level=1)
    
    # 1. Check if llama-cpp-python is installed
    try:
        import llama_cpp
        llama_installed = True
        typer.secho("✅ llama-cpp-python is installed and available.", fg="green")
    except ImportError:
        llama_installed = False
        typer.secho("✗ llama-cpp-python is NOT installed.", fg="red", bold=True)
        tip("To run local models, install it using: pip install teshq[local]")
        print_footer()
        return

    # 2. Detect hardware capabilities
    with status("Profiling host hardware...", success_message="Hardware profiling complete."):
        hw = detect_hardware()
        
    typer.echo("")
    typer.secho("💻 Hardware Detection Profile:", bold=True)
    typer.echo(f"  • CPU Cores:      {hw.cpu_cores}")
    typer.echo(f"  • Total RAM:      {hw.ram_total_gb} GB")
    typer.echo(f"  • Available RAM:  {hw.ram_available_gb} GB")
    if hw.gpu_name:
        typer.echo(f"  • GPU Model:      {hw.gpu_name}")
        typer.echo(f"  • GPU VRAM:       {hw.gpu_vram_mb} MB")
        typer.echo(f"  • GPU Backend:    {hw.gpu_backend.upper()}")
    else:
        typer.echo("  • GPU:            None detected (running entirely on CPU)")
    
    typer.echo("")
    typer.secho("🤖 Recommendations for your system:", bold=True)
    typer.echo(f"  • Suggested Model Size:  Sub-4B parameters (e.g. Qwen 3B/4B)")
    typer.echo(f"  • Suggested Quantization: {hw.recommended_quant}")
    typer.echo(f"  • GPU Layer Offload:     {hw.recommended_n_gpu_layers} layers")
    typer.echo(f"  • Context Size:          {hw.recommended_n_ctx} tokens")

    # 3. Check model configuration
    typer.echo("")
    typer.secho("⚙️ Current Configuration:", bold=True)
    s = get_settings()
    if s.local_model_path:
        typer.echo(f"  • LOCAL_MODEL_PATH:  {s.local_model_path}")
        import os
        if os.path.exists(s.local_model_path):
            size_gb = os.path.getsize(s.local_model_path) / (1024 ** 3)
            typer.secho(f"    ✅ File exists (Size: {size_gb:.2f} GB)", fg="green")
        else:
            typer.secho(f"    ✗ Model file does not exist at this path!", fg="red", bold=True)
            warning("Please check the path or run 'teshq pull' to fetch a default model.")
    else:
        typer.echo("  • LOCAL_MODEL_PATH:  Not configured (defaulting to empty)")
        warning("No local model is configured. Run 'teshq config --local' to configure one.")

    print_footer()

@app.command(name="test")
def local_test(
    prompt: str = typer.Option("Select 1 as test_val;", "--prompt", "-p", help="Prompt to run against the model."),
):
    """
    Perform a smoke test of the local GGUF runtime to verify speed and hardware acceleration.
    """
    print_header("Local Backend Smoke Test", level=1)
    
    # Check dependencies
    try:
        import llama_cpp
    except ImportError:
        error("llama-cpp-python is not installed. Run: pip install teshq[local]")
        raise typer.Exit(1)
        
    s = get_settings()
    if not s.local_model_path:
        error("LOCAL_MODEL_PATH is not configured in settings.")
        tip("Run: teshq config --local")
        raise typer.Exit(1)
        
    import os
    if not os.path.exists(s.local_model_path):
        error(f"GGUF model file not found at: '{s.local_model_path}'")
        tip("Run: teshq pull to download a GGUF model")
        raise typer.Exit(1)

    # Initialize runtime
    runtime = InferenceRuntime()
    config = InferenceConfig(
        model_path=s.local_model_path,
        n_ctx=s.local_n_ctx,
        n_gpu_layers=s.local_n_gpu_layers,
        n_threads=s.local_n_threads,
        verbose=False
    )
    
    try:
        with status("Loading model in-process (may take a few seconds)...", success_message="Model loaded successfully."):
            runtime.load(config)
            
        with status(f"Running generation for test prompt...", success_message="Generation finished."):
            result = runtime.generate(
                prompt=prompt,
                max_tokens=64,
                temperature=0.0
            )
            
        typer.echo("")
        typer.secho("📝 Prompt:", bold=True)
        typer.echo(f"  {prompt}")
        typer.echo("")
        typer.secho("✨ Generated Output:", bold=True)
        typer.secho(f"  {result.text}", fg="green")
        typer.echo("")
        typer.secho("📊 Performance Metrics:", bold=True)
        typer.echo(f"  • Latency:          {result.latency_ms:.2f} ms")
        typer.echo(f"  • Prompt Tokens:    {result.prompt_tokens}")
        typer.echo(f"  • Generated Tokens: {result.completion_tokens}")
        
        # Calculate tokens per second
        if result.latency_ms > 0 and result.completion_tokens > 0:
            tok_per_sec = (result.completion_tokens / result.latency_ms) * 1000
            typer.echo(f"  • Generation Speed: {tok_per_sec:.2f} tokens/sec")
            
    except Exception as e:
        error(f"Test failed with error: {e}")
        import traceback
        typer.echo(traceback.format_exc())
    finally:
        runtime.unload()
        
    print_footer("Test complete.")

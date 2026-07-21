import os
import shutil
import subprocess
import re
import webbrowser
import gradio as gr
from PIL import Image

def get_status_html(step, progress_percent=0):
    """Generates an EnterpriseDB-themed progress tracker with active stage progress bars."""
    steps = [
        ("⚙️ Staging", "Staging assets & linking workspace paths"),
        ("🎙️ Voice", "Cloning voice and generating narration WAV"),
        ("📟 VHS", "Running terminal emulator recording"),
        ("🎬 Compositing", "Adding watermarks, audio muxing & outputting MP4")
    ]
    
    html = '<div style="display: flex; gap: 10px; margin-bottom: 15px; font-family: sans-serif;">'
    for i, (name, desc) in enumerate(steps, start=1):
        is_active = i == step
        is_done = i < step
        
        # EnterpriseDB Palette Logic
        if is_done:
            bg, border, text = "#3E7CC2", "#2e64a1", "#ffffff" # EDB Primary Blue (Completed)
            bar_html = "" 
        elif is_active:
            bg, border, text = "#28495A", "#1e3744", "#ffffff" # EDB Deep Slate Blue (Active)
            bar_html = f"""
            <div style="margin-top: 8px; width: 100%; background-color: rgba(255,255,255,0.2); border-radius: 4px; height: 8px; overflow: hidden; position: relative;">
                <div style="width: {progress_percent}%; background-color: #3E7CC2; height: 100%; transition: width 0.3s ease;"></div>
            </div>
            <div style="font-size: 10px; margin-top: 4px; color: #a5f3fc; text-align: right; font-weight: bold;">{progress_percent}%</div>
            """
        else:
            bg, border, text = "#E9EBEC", "#d5d8da", "#5c6f84" # EDB Soft Light Gray (Pending)
            bar_html = ""
            
        html += f"""
        <div style="flex: 1; padding: 12px; border-radius: 6px; background-color: {bg}; border: 1px solid {border}; color: {text}; text-align: center; transition: all 0.3s ease; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
                <strong style="display: block; font-size: 14px; margin-bottom: 4px;">{name}</strong>
                <span style="font-size: 10px; opacity: 0.9;">{desc}</span>
            </div>
            {bar_html}
        </div>
        """
    html += '</div>'
    return html

def render_video_stream(
    demo_name, 
    narration_text, 
    demo_script, 
    use_custom_paths, 
    custom_script_path, 
    custom_narration_path,
    voice_input,
    image_input
):
    try:
        demo_dir = f"demos/{demo_name}"
        os.makedirs(demo_dir, exist_ok=True)
        
        yield None, "⚙️ Staging assets and linking your custom paths...", get_status_html(1, 100)
        
        log_accumulator = "⚙️ Staging assets...\n"
        
        if voice_input is not None:
            shutil.rmtree("voice-sample", ignore_errors=True)
            target_voice = "voice-sample/test_demo_voice.m4a"
            os.makedirs(os.path.dirname(target_voice), exist_ok=True)
            shutil.copy(voice_input, target_voice)
            log_accumulator += f"🎙️ Loaded presenter voice (saved to {target_voice}).\n"
            
        if image_input is not None:
            try:
                img = Image.open(image_input)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                    
                target_img_local = "assets/presenter.jpg"
                os.makedirs(os.path.dirname(target_img_local), exist_ok=True)
                img.save(target_img_local, "JPEG")
                img.save("assets/presenter.png", "PNG")
                log_accumulator += f"👤 Presenter headshot updated in {target_img_local}.\n"
                
                if use_custom_paths:
                    base_project_dir = os.path.abspath(os.path.join(custom_script_path.strip(), "../.."))
                    target_img_custom = os.path.join(base_project_dir, "assets/presenter.jpg")
                    if os.path.exists(os.path.dirname(target_img_custom)):
                        img.save(target_img_custom, "JPEG")
                        log_accumulator += f"👤 Synchronized headshot directly to custom workspace: {target_img_custom}.\n"
            except Exception as e:
                log_accumulator += f"⚠️ Image processing warning: {str(e)}\n"

        if use_custom_paths:
            script_source = custom_script_path.strip()
            narration_source = custom_narration_path.strip()
            
            if not os.path.exists(script_source):
                yield None, f"❌ Error: Script path does not exist: {script_source}", get_status_html(1, 0)
                return
            if not os.path.exists(narration_source):
                yield None, f"❌ Error: Narration path does not exist: {narration_source}", get_status_html(1, 0)
                return

            for f in ["demo.sh", "narration.txt"]:
                target = f"demos/{demo_name}/{f}"
                if os.path.islink(target) or os.path.exists(target):
                    try:
                        os.unlink(target) if os.path.islink(target) else os.remove(target)
                    except Exception:
                        pass

            os.symlink(script_source, f"demos/{demo_name}/demo.sh")
            os.symlink(narration_source, f"demos/{demo_name}/narration.txt")
        else:
            with open(f"{demo_dir}/narration.txt", "w") as f:
                f.write(narration_text)
            
            pace_header = """#!/bin/bash
source "${PACE_LIB:-/dev/null}" 2>/dev/null || true
type pace >/dev/null 2>&1 || pace() { :; }

"""
            with open(f"{demo_dir}/demo.sh", "w") as f:
                f.write(pace_header + demo_script)

        current_step = 2
        progress_percent = 0
        yield None, log_accumulator + "🚀 Starting render engine...\n", get_status_html(current_step, progress_percent)

        try:
            process = subprocess.Popen(
                ["bash", "./render.sh", demo_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
        except Exception as e:
            error_msg = f"❌ Failed to launch render engine process: {str(e)}\nEnsure render.sh exists in this directory."
            yield None, log_accumulator + error_msg, get_status_html(current_step, 0)
            return

        for line in iter(process.stdout.readline, ""):
            log_accumulator += line
            
            if "recording terminal" in line.lower():
                current_step = 3
                progress_percent = 0
            elif "muxing" in line.lower() or "ffmpeg" in line.lower() or "joining" in line.lower():
                current_step = 4
                progress_percent = 50 
                
            sampling_match = re.search(r"Sampling:\s+(\d+)%", line)
            if sampling_match and current_step == 2:
                progress_percent = int(sampling_match.group(1))
                
            vhs_match = re.search(r"Rendered\s+(\d+)%", line)
            if vhs_match and current_step == 3:
                progress_percent = int(vhs_match.group(1))

            if current_step == 4 and "saved" in line.lower():
                progress_percent = 100

            yield None, log_accumulator, get_status_html(current_step, progress_percent)

        process.stdout.close()
        return_code = process.wait()

        video_path = f"build/video/{demo_name}.mp4"
        if return_code == 0 and os.path.exists(video_path):
            log_accumulator += "\n🎉 Video rendering complete!"
            yield video_path, log_accumulator, get_status_html(4, 100)
        else:
            log_accumulator += f"\n❌ Rendering failed with exit code {return_code}."
            yield None, log_accumulator, get_status_html(current_step, progress_percent)

    except Exception as fatal_e:
        # Catches any unexpected Python error so the UI display never breaks
        error_log = f"❌ Fatal Exception: {str(fatal_e)}"
        yield None, error_log, get_status_html(1, 0)

# EDB Color Styled Panel Theme
edb_theme = gr.themes.Default(
    primary_hue="blue",
    neutral_hue="slate",
).set(
    button_primary_background_fill="#3E7CC2",
    button_primary_background_fill_hover="#2e64a1",
    block_background_fill="#E9EBEC",
    block_border_color="#d5d8da"
)

# Custom HTML Banner
contact_banner_html = """
<div style="background-color: #28495A; border-left: 6px solid #3E7CC2; padding: 12px 20px; border-radius: 4px; margin-bottom: 20px; font-family: sans-serif; color: #ffffff; display: flex; justify-content: space-between; align-items: center;">
    <div>
        <span style="font-size: 14px; font-weight: bold; display: block; color: #ffffff; margin-bottom: 2px;">💡 Have suggestions or feature ideas?</span>
        <span style="font-size: 12px; color: #E9EBEC; opacity: 0.9;">Help improve the studio tool by sharing feedback or reporting operational issues.</span>
    </div>
    <div style="text-align: right;">
        <a href="mailto:ram.srinivasan@enterprisedb.com" style="background-color: #3E7CC2; color: #ffffff; padding: 8px 14px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: bold; border: 1px solid #2e64a1; transition: background-color 0.2s ease;">📬 Reach Out to Ram</a>
    </div>
</div>
"""

with gr.Blocks(title="Demo Video Maker Studio", theme=edb_theme) as demo:
    gr.Markdown("# 🎬 Demo Video Maker Studio")
    
    # Render the interactive Support and Feedback Banner
    gr.HTML(value=contact_banner_html)
    
    # Live progress tracking boxes
    status_tracker = gr.HTML(value=get_status_html(0))
    
    with gr.Row():
        with gr.Column(scale=1):
            demo_name = gr.Textbox(label="📁 Project Name", value="semanticiq-demo")
            
            with gr.Row():
                voice_source = gr.Audio(
                    label="🎙️ Live Presenter Voice (Record or Upload)", 
                    sources=["microphone", "upload"], 
                    type="filepath"
                )
                image_source = gr.Image(
                    label="👤 Presenter Headshot (Webcam or Upload)", 
                    sources=["webcam", "upload"], 
                    type="filepath"
                )
            
            use_custom = gr.Checkbox(label="🔗 Use existing local system paths", value=True)
            
            with gr.Group() as path_inputs:
                gr.Markdown("### Local Workspace Paths")
                script_path = gr.Textbox(
                    label="Absolute Path to your demo.sh",
                    value="/Users/ram.srinivasan/testmydemorepo/demo-test-clean/demos/make-a-demo/demo.sh"
                )
                narration_path = gr.Textbox(
                    label="Absolute Path to your narration.txt",
                    value="/Users/ram.srinivasan/testmydemorepo/demo-test-clean/demos/make-a-demo/narration.txt"
                )
            
            with gr.Group(visible=False) as text_inputs:
                gr.Markdown("### Scratchpad Editors")
                narration_text = gr.Textbox(label="Narration Script", lines=4, placeholder="Type your voiceover...")
                demo_script = gr.Textbox(label="Bash Commands", lines=6, placeholder="echo 'Hello'\npace 10")

            render_btn = gr.Button("Generate Video 🚀", variant="primary")
            
        with gr.Column(scale=1):
            video_output = gr.Video(label="📺 Generated Video")
            logs_output = gr.Textbox(label="📟 Real-Time Execution Logs", lines=25, max_lines=35, interactive=False)

    def toggle_inputs(checked):
        return gr.update(visible=checked), gr.update(visible=not checked)
        
    use_custom.change(
        fn=toggle_inputs,
        inputs=[use_custom],
        outputs=[path_inputs, text_inputs]
    )

    render_btn.click(
        fn=render_video_stream, 
        inputs=[
            demo_name, 
            narration_text, 
            demo_script, 
            use_custom, 
            script_path, 
            narration_path,
            voice_source,
            image_source
        ], 
        outputs=[video_output, logs_output, status_tracker]
    )

if __name__ == "__main__":
    webbrowser.open_new_tab("http://127.0.0.1:7860")
    demo.launch(server_name="127.0.0.1", server_port=7860)
import keyboard
import pyperclip
import pyautogui
import tkinter as tk
from tkinter import scrolledtext, font, ttk
from openai import OpenAI
import groq
import os
from config import OPENAI_API_KEY, GROQ_API_KEY, LOCAL_LLM_URL, SYSTEM_PROMPT
from pystray import Icon as TrayIcon, Menu as TrayMenu, MenuItem as TrayMenuItem
from PIL import Image
import threading
import requests
from screeninfo import get_monitors

# Set your API keys as environment variables
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["GROQ_API_KEY"] = GROQ_API_KEY

# Initialize the clients
openai_client = OpenAI()
groq_client = groq.Groq()

# Define available models
MODELS = {
    "Groq": ["llama-3.2-90b-text-preview", "llama-3.1-8b-instant", "gemma2-9b-it", "mixtral-8x7b-32768"],
    "OpenAI": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
    "Local LLM": ["llama3.2", "custom"]  # Add your local model names here
}

# Define predefined prompts
PREDEFINED_PROMPTS = [
    "Custom prompt",
    "Paraphrase the following text",
    "Translate the following text to English",
    "Translate the following text to Spanish",
    "Summarize the following text",
    "Explain the following concept"
]

# Initialize system_prompt from config
system_prompt = SYSTEM_PROMPT

def show_dialog():
    dialog = tk.Toplevel()
    dialog.title("AI Assistant")
    
    # Get the current mouse position
    mouse_x, mouse_y = pyautogui.position()
    
    # Get the screen where the mouse is
    current_screen = None
    for monitor in get_monitors():
        if (monitor.x <= mouse_x <= monitor.x + monitor.width and
            monitor.y <= mouse_y <= monitor.y + monitor.height):
            current_screen = monitor
            break
    
    # If no screen is found, use the primary monitor
    if not current_screen:
        current_screen = get_monitors()[0]
    
    # Increase default font size
    default_font = font.nametofont("TkDefaultFont")
    default_font.configure(size=12)
    dialog.option_add("*Font", default_font)
    
    # Set a fixed size for the dialog based on the text area dimensions
    dialog_width = 1000  # Slightly wider to accommodate the text area width
    dialog_height = 600  # Taller to ensure all elements fit
    
    # Calculate position to center on screen
    x = current_screen.x + (current_screen.width - dialog_width) // 2
    y = current_screen.y + (current_screen.height - dialog_height) // 2
    
    # Set geometry
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    # Prevent resizing
    dialog.resizable(False, False)
    
    # Create a main frame to hold all elements
    main_frame = tk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # Create a frame for the API, model, and prompt choice
    choice_frame = tk.Frame(main_frame)
    choice_frame.pack(fill=tk.X, pady=(0, 10))
    
    # Create and pack the AI choice dropdown
    api_label = tk.Label(choice_frame, text="AI:")
    api_label.grid(row=0, column=0, padx=(0, 5), sticky="w")
    api_var = tk.StringVar(value="Groq")
    api_dropdown = ttk.Combobox(choice_frame, textvariable=api_var, values=list(MODELS.keys()), state="readonly")
    api_dropdown.grid(row=0, column=1, sticky="ew")
    
    # Create and pack the Model choice dropdown
    model_label = tk.Label(choice_frame, text="Model:")
    model_label.grid(row=0, column=2, padx=(10, 5), sticky="w")
    model_var = tk.StringVar(value=MODELS["Groq"][0])
    model_dropdown = ttk.Combobox(choice_frame, textvariable=model_var, values=MODELS["Groq"], state="readonly")
    model_dropdown.grid(row=0, column=3, sticky="ew")
    
    # Create and pack the Prompt choice dropdown
    prompt_label = tk.Label(choice_frame, text="Prompt:")
    prompt_label.grid(row=1, column=0, padx=(0, 5), sticky="w", pady=(10, 0))
    prompt_var = tk.StringVar(value=PREDEFINED_PROMPTS[0])
    prompt_dropdown = ttk.Combobox(choice_frame, textvariable=prompt_var, values=PREDEFINED_PROMPTS, state="readonly")
    prompt_dropdown.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(10, 0))
    
    # Configure grid
    choice_frame.columnconfigure(1, weight=1)
    choice_frame.columnconfigure(3, weight=1)
    
    # Add prompt label
    custom_prompt_label = tk.Label(main_frame, text="Enter your prompt or text:")
    custom_prompt_label.pack(anchor="w", pady=(0, 5))
    
    # Create and configure the text area
    text_area = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=52, height=6)
    text_area.pack(fill=tk.BOTH, expand=True)
    text_area.configure(font=("TkDefaultFont", 12))
    
    def update_model_choices(*args):
        selected_api = api_var.get()
        model_dropdown['values'] = MODELS[selected_api]
        model_var.set(MODELS[selected_api][0])
    
    api_var.trace('w', update_model_choices)
    
    def update_text_area(*args):
        selected_prompt = prompt_var.get()
        if selected_prompt != "Custom prompt":
            text_area.delete("1.0", tk.END)
            text_area.insert(tk.END, f"{selected_prompt}:\n")
    
    prompt_var.trace('w', update_text_area)
    
    def on_submit():
        prompt = text_area.get("1.0", tk.END).strip()
        api_choice = api_var.get()
        model_choice = model_var.get()
        dialog.destroy()
        process_prompt(prompt, api_choice, model_choice)
    
    def on_cancel():
        dialog.destroy()
    
    # Bind the Enter key to submit
    dialog.bind('<Return>', lambda event: on_submit())
    
    # Create a frame for buttons
    button_frame = tk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(10, 0))
    
    # Create and pack the Submit and Cancel buttons with increased width
    submit_button = tk.Button(button_frame, text="Cancel", command=on_cancel, width=20)
    submit_button.pack(side=tk.LEFT, expand=True, padx=5)
    cancel_button = tk.Button(button_frame, text="Submit", command=on_submit, width=20)
    cancel_button.pack(side=tk.RIGHT, expand=True, padx=5)
    
    dialog.focus_force()
    dialog.mainloop()

def process_prompt(prompt, api_choice, model_choice):
    global system_prompt
    if prompt:
        try:
            if api_choice == "OpenAI":
                response = openai_client.chat.completions.create(
                    model=model_choice,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                )
                generated_text = response.choices[0].message.content.strip()
            elif api_choice == "Groq":
                completion = groq_client.chat.completions.create(
                    model=model_choice,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ]
                )
                generated_text = completion.choices[0].message.content.strip()
            elif api_choice == "Local LLM":
                response = requests.post(
                    LOCAL_LLM_URL,
                    json={
                        "model": model_choice,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ]
                    }
                )
                response.raise_for_status()
                generated_text = response.json()['choices'][0]['message']['content'].strip()
            
            pyperclip.copy(generated_text)
            pyautogui.hotkey('ctrl', 'v')
        except Exception as e:
            show_error_message(f"An error occurred: {str(e)}")

def show_error_message(message):
    dialog = tk.Toplevel()
    dialog.title("Error")
    label = tk.Label(dialog, text=message, padx=20, pady=10)
    label.pack()
    ok_button = tk.Button(dialog, text="OK", command=dialog.destroy)
    ok_button.pack(pady=10)
    dialog.focus_force()

def on_hotkey():
    root.after(0, show_dialog)

def create_image():
    # Create a simple image for the tray icon
    image = Image.new('RGB', (64, 64), color = (73, 109, 137))
    return image

def exit_action(icon):
    icon.stop()
    root.quit()

def show_system_prompt_dialog():
    global system_prompt
    dialog = tk.Toplevel()
    dialog.title("Set System Prompt")
    
    # Increase default font size for this dialog
    default_font = font.nametofont("TkDefaultFont")
    default_font.configure(size=14)  # Adjust this value to change the overall text size
    dialog.option_add("*Font", default_font)
    
    # Set dialog size and position
    dialog_width = 1000  # Adjust this value to change the dialog width
    dialog_height = 600  # Adjust this value to change the dialog height
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width - dialog_width) // 2
    y = (screen_height - dialog_height) // 2
    dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    # Create and pack the text area
    prompt_label = tk.Label(dialog, text="Enter the system prompt:")
    prompt_label.pack(pady=(10, 5))
    text_area = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, width=60, height=10)
    text_area.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
    text_area.configure(font=("TkDefaultFont", 14))  # Adjust 14 to your preferred size
    text_area.insert(tk.END, system_prompt)
    
    def save_prompt():
        global system_prompt
        new_prompt = text_area.get("1.0", tk.END).strip()
        if new_prompt != system_prompt:
            system_prompt = new_prompt
            update_config_file(new_prompt)
        dialog.destroy()
    
    # Create and pack the Save button
    save_button = tk.Button(dialog, text="Save", command=save_prompt)
    save_button.pack(pady=10)
    
    dialog.focus_force()
    dialog.mainloop()

def update_config_file(new_prompt):
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    with open(config_path, 'r') as file:
        lines = file.readlines()
    
    for i, line in enumerate(lines):
        if line.startswith('SYSTEM_PROMPT'):
            lines[i] = f'SYSTEM_PROMPT = "{new_prompt}"\n'
            break
    else:
        lines.append(f'SYSTEM_PROMPT = "{new_prompt}"\n')
    
    with open(config_path, 'w') as file:
        file.writelines(lines)

def setup_tray_icon():
    image = create_image()
    menu = TrayMenu(
        TrayMenuItem('Show Dialog', lambda: root.after(0, show_dialog)),
        TrayMenuItem('System Prompt', lambda: root.after(0, show_system_prompt_dialog)),
        TrayMenuItem('Exit', exit_action)
    )
    icon = TrayIcon("AI Assistant", image, "AI Assistant", menu)
    return icon

def run_tray_icon(icon):
    icon.run()

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Set up the hotkey to use the Insert key
    keyboard.add_hotkey('ctrl+insert', on_hotkey)
    
    # Create and run the system tray icon
    icon = setup_tray_icon()
    
    # Run the tray icon in a separate thread
    tray_thread = threading.Thread(target=run_tray_icon, args=(icon,))
    tray_thread.start()
    
    # Start the Tkinter event loop
    root.mainloop()

import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
import os

CONFIG_DIR_NAME = ".ii_agent"
CONFIG_FILE_NAME = "config.json"

# Define required keys
DEFAULT_REQUIRED_KEYS = [
    "ANTHROPIC_API_KEY",
    "TAVILY_API_KEY",
    # Add other essential keys here if known, e.g., from .env.example
    # "FIREBASE_API_KEY",
    # "GOOGLE_API_KEY", # Example
]

def get_config_path():
    home = Path.home()
    config_dir = home / CONFIG_DIR_NAME
    return config_dir / CONFIG_FILE_NAME

def load_config():
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {} # Corrupted file
    return {}

def save_config(config_data):
    config_path = get_config_path()
    config_dir = config_path.parent
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)
    except OSError as e:
        messagebox.showerror("Config Error", f"Failed to save config: {e}")


def ask_for_keys_gui(required_keys, current_config=None):
    if current_config is None:
        current_config = {}

    new_config = current_config.copy()

    root = tk.Tk()
    root.title("API Key Configuration")
    root.withdraw() # Hide main window initially

    # Create a dialog-like top-level window
    dialog = tk.Toplevel(root)
    dialog.title("Enter API Keys")
    dialog.transient(root) # Keep dialog on top of a (hidden) parent
    dialog.grab_set() # Modal behavior

    entries = {}

    main_frame = ttk.Frame(dialog, padding="10 10 10 10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    ttk.Label(main_frame, text="Please enter the required API keys:").grid(row=0, column=0, columnspan=2, pady=10)

    for i, key_name in enumerate(required_keys):
        ttk.Label(main_frame, text=f"{key_name}:").grid(row=i + 1, column=0, sticky=tk.W, padx=5, pady=5)
        entry = ttk.Entry(main_frame, width=50)
        entry.grid(row=i + 1, column=1, sticky=tk.EW, padx=5, pady=5)
        if key_name in new_config:
            entry.insert(0, new_config[key_name])
        entries[key_name] = entry

    def on_save():
        all_filled = True
        for key_name, entry_widget in entries.items():
            value = entry_widget.get().strip()
            if not value and key_name in required_keys : # Only enforce for truly required keys
                messagebox.showwarning("Missing Key", f"API key for '{key_name}' is required.", parent=dialog)
                all_filled = False
                entry_widget.focus_set()
                return
            new_config[key_name] = value

        if all_filled:
            save_config(new_config)
            messagebox.showinfo("Success", "API keys saved.", parent=dialog)
            dialog.destroy()
            root.destroy() # Close the hidden root window as well

    def on_cancel():
        # If cancelled, we don't save, existing new_config (which might be empty) is returned implicitly
        dialog.destroy()
        root.destroy()


    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=len(required_keys) + 1, column=0, columnspan=2, pady=10)

    save_button = ttk.Button(button_frame, text="Save", command=on_save)
    save_button.pack(side=tk.LEFT, padx=5)

    cancel_button = ttk.Button(button_frame, text="Cancel", command=on_cancel)
    cancel_button.pack(side=tk.LEFT, padx=5)

    dialog.protocol("WM_DELETE_WINDOW", on_cancel) # Handle window close button
    dialog.wait_window() # Wait for dialog to close

    return new_config


def ensure_api_keys(required_keys_list=None):
    if required_keys_list is None:
        required_keys_list = DEFAULT_REQUIRED_KEYS

    current_conf = load_config()

    missing_keys = False
    for key in required_keys_list:
        if not current_conf.get(key): # Check if key exists and is not empty
            missing_keys = True
            break

    if missing_keys:
        print("API keys missing or incomplete. Launching configuration UI...")
        # Pass current_conf so it can pre-fill any existing values
        updated_config = ask_for_keys_gui(required_keys_list, current_conf)
        # Check again if required keys are now present after UI interaction
        final_check_missing = False
        for key in required_keys_list:
            if not updated_config.get(key):
                final_check_missing = True
                break
        if final_check_missing:
            print("Configuration cancelled or required keys still missing. Application might not function correctly.")
            # Decide on behavior: exit, or return empty/partial config? For now, return what we have.
            return updated_config
        return updated_config

    print("API keys loaded successfully.")
    return current_conf

if __name__ == '__main__':
    # Example usage:
    print("Checking API keys...")
    config = ensure_api_keys()
    if config.get("ANTHROPIC_API_KEY"):
        print(f"Anthropic Key found: {config.get('ANTHROPIC_API_KEY')[:5]}...")
    else:
        print("Anthropic Key not found or not provided.")

    if config.get("TAVILY_API_KEY"):
        print(f"Tavily Key found: {config.get('TAVILY_API_KEY')[:5]}...")
    else:
        print("Tavily Key not found or not provided.")
    print("Full config loaded:", config)

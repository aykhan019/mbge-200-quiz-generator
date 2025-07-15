import re
import sys
import os
import json
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox

#############################################
# Before we define constants, we need to know which PS sets are available.
# We'll scan the base_path (the folder containing this script or the PyInstaller bundle)
# for directories that start with "ps" and are not "assets".
#############################################

if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    base_path = sys._MEIPASS
else:
    # Running in normal Python
    base_path = os.path.dirname(os.path.abspath(__file__))

all_dirs = [
    d for d in os.listdir(base_path)
    if os.path.isdir(os.path.join(base_path, d))
    and d.startswith("ps")
    and d != "assets"
]

if not all_dirs:
    print("No problem sets found.")
    sys.exit(1)

#############################################
# A more beautiful selection window to pick a PS set from the list `all_dirs`.
#############################################
class PSSelector(tk.Toplevel):
    def __init__(self, master, ps_list):
        super().__init__(master)
        self.title("Select Problem Set")

        # Set a nicer size for our selection window
        self.geometry("450x350")
        self.update_idletasks()

        # Center the window on the screen
        width = 700
        height = 500
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Give the window a light background color
        self.config(bg="#f0f0f0")

        # Use a StringVar to hold the user-selected PS set
        self.ps_var = tk.StringVar(value=ps_list[0])

        # Title label
        title_label = tk.Label(
            self, 
            text="Select a Problem Set", 
            font=("Helvetica", 20, "bold"), 
            bg="#f0f0f0"
        )
        title_label.pack(pady=20)

        # A frame to contain the radio buttons
        radio_frame = tk.Frame(self, bg="#f0f0f0")
        radio_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        # Create radio buttons for each PS directory
        for ps_name in ps_list:
            rb = tk.Radiobutton(
                radio_frame, 
                text=ps_name,
                variable=self.ps_var, 
                value=ps_name, 
                font=("Helvetica", 14),
                bg="#f0f0f0",
                activebackground="#e0e0e0",
                anchor='w',
                padx=10
            )
            rb.pack(anchor='w', pady=5, fill=tk.X)

        # A 'Select' button at the bottom
        select_button = tk.Button(
            self, 
            text="Select", 
            command=self.on_select,
            font=("Helvetica", 14, "bold"),
            bg="#007acc",
            fg="white",
            relief="raised",
            bd=3
        )
        select_button.pack(pady=20)

        self.selected_ps = None

    def on_select(self):
        self.selected_ps = self.ps_var.get()
        self.destroy()


# First, show a hidden main root, then create the selection window.
root_prompt = tk.Tk()
root_prompt.withdraw()
selector = PSSelector(root_prompt, all_dirs)
root_prompt.wait_window(selector)
PS = selector.selected_ps
root_prompt.destroy()

if not PS or PS not in all_dirs:
    print("Invalid problem set selection.")
    sys.exit(1)

#############################################
# Configuration
#############################################
SOURCE_FILE = os.path.join(base_path, PS, "source.txt")
SCENARIO_FILE = os.path.join(base_path, PS, "scenarios.txt")
FIGURE_DIR = os.path.join(base_path, PS, "images", "figures")
TABLE_DIR = os.path.join(base_path, PS, "images", "tables")
SESSION_FILE = "session.json"
LEFT_AD_IMAGE = "assets/left_ad.png"
RIGHT_AD_IMAGE = "assets/right_ad.png"

#############################################
# Parse Scenarios
#############################################
scenario_dict = {}

if os.path.exists(SCENARIO_FILE):
    with open(SCENARIO_FILE, "r", encoding="utf-8") as sf:
        lines = [line.rstrip('\n') for line in sf]
        current_scenario_key = None
        current_scenario_text = []

        for line in lines:
            # Modified regex to also capture any trailing text after the scenario title
            scenario_match = re.match(r"\*\*\*Scenario\s+(\d+-\d+)\*\*\*(.*)", line, re.IGNORECASE)
            if scenario_match:
                # If we were processing another scenario, save it first
                if current_scenario_key:
                    scenario_dict[current_scenario_key] = "\n".join(current_scenario_text).strip()

                # Start a new scenario
                current_scenario_key = scenario_match.group(1)
                current_scenario_text = []
                trailing_text = scenario_match.group(2).strip()
                if trailing_text:
                    current_scenario_text.append(trailing_text)
            else:
                if current_scenario_key:
                    current_scenario_text.append(line)

        # Save the last scenario if there is one
        if current_scenario_key:
            scenario_dict[current_scenario_key] = "\n".join(current_scenario_text).strip()
else:
    print(f"Warning: Scenario file '{SCENARIO_FILE}' not found. Scenario questions won't have scenario text.")
    scenario_dict = {}

#############################################
# Parse Questions
#############################################
all_text = ""
try:
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        all_text = f.read()
except FileNotFoundError:
    print(f"Error: File {SOURCE_FILE} not found.")
    sys.exit(1)

lines = [line.strip() for line in all_text.split('\n') if line.strip()]

questions = []
current_question = None
current_choices = {}

for line in lines:
    ans_match = re.search(r"ANS:\s*([A-Da-d])", line)
    if ans_match:
        correct_answer = ans_match.group(1).lower()
        if current_question and current_choices:
            questions.append({
                "question": current_question.strip(),
                "choices": current_choices,
                "answer": correct_answer
            })
        current_question = None
        current_choices = {}
        continue

    choice_match = re.match(r"([a-d])\.\s*(.*)", line, re.IGNORECASE)
    if choice_match:
        choice_letter = choice_match.group(1).lower()
        choice_text = choice_match.group(2).strip()
        current_choices[choice_letter] = choice_text
    else:
        if current_question:
            current_question += " " + line
        else:
            current_question = line

#############################################
# Determine question type (figure/table/scenario/normal)
#############################################
def identify_question_type(question_text):
    fig_match = re.search(r"Refer to Figure\s+(\d+-\d+)", question_text, re.IGNORECASE)
    if fig_match:
        return ("figure", fig_match.group(1))
    table_match = re.search(r"Refer to Table\s+(\d+-\d+)", question_text, re.IGNORECASE)
    if table_match:
        return ("table", table_match.group(1))
    scenario_match = re.search(r"Refer to Scenario\s+(\d+-\d+)", question_text, re.IGNORECASE)
    if scenario_match:
        return ("scenario", scenario_match.group(1))
    return ("normal", None)

#############################################
# Session Handling
#############################################
def load_session():
    current_index = 0
    finished_count = 0
    correctness = {}
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            ps_data = data.get(PS, {})
            current_index = ps_data.get("current_index", 0)
            finished_count = ps_data.get("finished_count", 0)
            correctness_list = ps_data.get("correctness", [])
            correctness = {k: v for k, v in correctness_list}
    return current_index, finished_count, correctness

def save_session(index, finished_count, correctness):
    session_data = {}
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            session_data = json.load(f)

    correctness_list = [(k, v) for k, v in correctness.items()]
    session_data[PS] = {
        "current_index": index,
        "finished_count": finished_count,
        "correctness": correctness_list
    }

    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(session_data, f)

#############################################
# Helper to load and tile ad images
#############################################
def load_ad_image(path):
    if os.path.exists(path):
        img = Image.open(path)
        # Resize to a fixed width for the ad
        img = img.resize((200, 400), Image.Resampling.LANCZOS)
        return img
    return None

def tile_image_vertically(base_img, height):
    if not base_img:
        return None
    w, h = base_img.size
    times = (height // h) + 1
    new_img = Image.new('RGB', (w, max(h, height)), color=(255, 255, 255))
    y_offset = 0
    for _ in range(times):
        new_img.paste(base_img, (0, y_offset))
        y_offset += h
        if y_offset >= height:
            break
    if new_img.size[1] > height:
        new_img = new_img.crop((0, 0, w, height))
    return ImageTk.PhotoImage(new_img)

#############################################
# GUI Quiz Application
#############################################
class QuizApp:
    def __init__(self, master, questions, scenarios, figure_dir, table_dir, start_index=0, finished_count=0, correctness=None):
        self.master = master
        self.questions = questions
        self.scenarios = scenarios
        self.figure_dir = figure_dir
        self.table_dir = table_dir
        self.index = start_index if 0 <= start_index < len(self.questions) else 0
        self.score = 0
        self.num_questions = len(self.questions)
        self.finished_count = finished_count
        self.correctness = correctness if correctness is not None else {}

        self.master.attributes('-fullscreen', True)

        self.main_frame = tk.Frame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.left_ad_frame = tk.Frame(self.main_frame, width=200)
        self.left_ad_frame.pack(side=tk.LEFT, fill=tk.BOTH)

        self.center_frame = tk.Frame(self.main_frame)
        self.center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.right_ad_frame = tk.Frame(self.main_frame, width=200)
        self.right_ad_frame.pack(side=tk.LEFT, fill=tk.BOTH)

        self.left_ad_img = load_ad_image(LEFT_AD_IMAGE)
        self.right_ad_img = load_ad_image(RIGHT_AD_IMAGE)

        self.left_ad_label = tk.Label(self.left_ad_frame, bg="white")
        self.left_ad_label.pack(fill=tk.BOTH, expand=True)

        self.right_ad_label = tk.Label(self.right_ad_frame, bg="white")
        self.right_ad_label.pack(fill=tk.BOTH, expand=True)

        self.left_ad_frame.bind("<Configure>", self.update_left_ad)
        self.right_ad_frame.bind("<Configure>", self.update_right_ad)

        question_font = ("Arial", 24, "bold")
        scenario_font = ("Arial", 20)
        choice_font = ("Arial", 20)
        button_font = ("Arial", 20, "bold")

        # Canvas and scrollbar for scrolling
        self.content_canvas = tk.Canvas(self.center_frame)
        self.content_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.content_frame = tk.Frame(self.content_canvas)
        self.content_window = self.content_canvas.create_window((0, 0), window=self.content_frame, anchor='nw')

        self.content_canvas.bind("<Configure>", self.on_canvas_configure)

        def on_content_frame_configure(event):
            self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        self.content_frame.bind("<Configure>", on_content_frame_configure)

        # Inner frame for centering the container
        self.inner_frame = tk.Frame(self.content_frame, bd=2, relief='solid')
        self.inner_frame.pack(fill=tk.X)
        self.inner_frame.pack_propagate(False)
        self.inner_frame.config(height=1000)

        self.scrollbar = tk.Scrollbar(self.inner_frame, orient="vertical", command=self.content_canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.content_canvas.configure(yscrollcommand=self.scrollbar.set)

        # Image top
        self.image_label = tk.Label(self.inner_frame)
        self.image_label.pack(pady=0)

        self.scenario_label = tk.Label(
            self.inner_frame, 
            text="", 
            font=scenario_font, 
            justify=tk.LEFT, 
            wraplength=700, 
            anchor='w'
        )
        self.scenario_label.pack(pady=5)

        # Question label
        self.question_label = tk.Label(
            self.inner_frame, 
            text="", 
            font=question_font, 
            wraplength=700, 
            justify=tk.LEFT, 
            anchor='w'
        )
        self.question_label.pack(pady=10)

        self.var = tk.StringVar(value='')

        # Choices frame
        self.choice_frame = tk.Frame(self.inner_frame)
        self.choice_frame.pack(pady=10)

        self.choice_buttons = []
        for i in range(4):
            rb = tk.Radiobutton(
                self.choice_frame, 
                text="", 
                variable=self.var, 
                value="", 
                font=choice_font, 
                wraplength=700, 
                anchor='w', 
                justify=tk.LEFT
            )
            rb.pack(anchor='w', pady=5)
            self.choice_buttons.append(rb)

        self.buttons_frame = tk.Frame(self.center_frame)
        self.buttons_frame.pack(side=tk.TOP, pady=10)

        # Navigation and submit buttons
        self.prev_button = tk.Button(
            self.buttons_frame,
            text="←",
            command=self.prev_question,
            font=button_font,
            bg="lightblue",
            fg="black"
        )
        self.prev_button.grid(row=0, column=0, padx=10)

        self.submit_button = tk.Button(
            self.buttons_frame,
            text="Submit",
            command=self.check_answer,
            font=button_font,
            bg="lightblue",
            fg="black"
        )
        self.submit_button.grid(row=0, column=1, padx=10)

        self.next_button = tk.Button(
            self.buttons_frame,
            text="→",
            command=self.next_question,
            font=button_font,
            bg="lightblue",
            fg="black"
        )
        self.next_button.grid(row=0, column=2, padx=10)

        self.result_label = tk.Label(
            self.inner_frame, 
            text="", 
            font=("Arial", 20), 
            justify=tk.LEFT, 
            anchor='w'
        )
        self.result_label.pack(pady=10)

        self.scoreboard_frame = tk.Frame(self.center_frame)
        self.scoreboard_frame.pack(side=tk.BOTTOM, pady=10)

        self.question_status = []
        for i in range(self.num_questions):
            lbl = tk.Label(
                self.scoreboard_frame,
                text=str(i+1),
                width=4,
                height=2,
                bg="gray",
                font=("Arial", 14, "bold")
            )
            self.question_status.append(lbl)

        self.load_question(self.index)
        self.master.bind("<Escape>", self.exit_fullscreen)

        # Restore previous correctness states
        self.restore_correctness()

    def restore_correctness(self):
        for i, lbl in enumerate(self.question_status):
            if i in self.correctness:
                if self.correctness[i]:
                    lbl.config(bg="green")
                else:
                    lbl.config(bg="red")

    def on_canvas_configure(self, event):
        self.content_canvas.itemconfig(self.content_window, width=event.width)

    def exit_fullscreen(self, event=None):
        self.master.attributes('-fullscreen', False)

    def update_left_ad(self, event):
        if self.left_ad_img:
            tiled = tile_image_vertically(self.left_ad_img, event.height)
            if tiled:
                self.left_ad_label.config(image=tiled)
                self.left_ad_label.image = tiled
            else:
                self.left_ad_label.config(text="Ads Here")
        else:
            self.left_ad_label.config(text="Ads Here")

    def update_right_ad(self, event):
        if self.right_ad_img:
            tiled = tile_image_vertically(self.right_ad_img, event.height)
            if tiled:
                self.right_ad_label.config(image=tiled)
                self.right_ad_label.image = tiled
            else:
                self.right_ad_label.config(text="Ads Here")
        else:
            self.right_ad_label.config(text="Ads Here")

    def load_image(self, path):
        if os.path.exists(path):
            img = Image.open(path)
            min_width = 200
            min_height = 200
            max_width = 400
            max_height = 350
            w, h = img.size

            if w < min_width or h < min_height:
                ratio = max(min_width / w, min_height / h)
                new_width = int(w * ratio)
                new_height = int(h * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            elif w > max_width or h > max_height:
                ratio = min(max_width / w, max_height / h)
                new_width = int(w * ratio)
                new_height = int(h * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            self.photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.photo, text="")
            self.image_label.image = self.photo
        else:
            self.image_label.config(image="", text="(Image not found)")

    def load_question(self, idx):
        if idx < 0:
            self.index = 0
        if idx >= len(self.questions):
            self.show_score()
            return

        self.var.set('')
        q = self.questions[idx]
        q_type, q_ref = identify_question_type(q["question"])

        self.image_label.config(image="", text="")
        self.result_label.config(text="", fg="black")
        self.scenario_label.config(text="")
        self.question_label.config(text="")

        if q_type == "figure":
            figure_path = os.path.join(self.figure_dir, f"figure{q_ref}.png")
            self.load_image(figure_path)
        elif q_type == "table":
            table_path = os.path.join(self.table_dir, f"table{q_ref}.png")
            self.load_image(table_path)
        elif q_type == "scenario":
            scenario_text = self.scenarios.get(q_ref, "(Scenario not found)")
            self.scenario_label.config(text=scenario_text)

        self.question_label.config(text=f"{self.index+1}. {q['question']}")

        keys = list(q["choices"].keys())
        for i, rb in enumerate(self.choice_buttons):
            if i < len(keys):
                rb.config(text=f"{keys[i]}) {q['choices'][keys[i]]}", value=keys[i], state="normal")
                rb.deselect()
            else:
                rb.config(text="", value="", state="disabled")
                rb.deselect()

        self.submit_button.config(state="normal")
        self.next_button.config(state="normal")

        if self.index == 0:
            self.prev_button.config(state="disabled")
        else:
            self.prev_button.config(state="normal")

        self.update_scoreboard()
        self.master.update_idletasks()

    def update_scoreboard(self):
        for lbl in self.question_status:
            lbl.pack_forget()

        # Show only a window of question labels around the current index
        start = max(0, self.index - 5)
        end = min(self.num_questions, self.index + 5 + 1)
        for i in range(start, end):
            self.question_status[i].pack(side=tk.LEFT, padx=5)

        # Color them if we already answered them
        for i, lbl in enumerate(self.question_status):
            if i in self.correctness:
                if self.correctness[i]:
                    lbl.config(bg="green")
                else:
                    lbl.config(bg="red")

    def check_answer(self):
        if self.index < len(self.questions):
            q = self.questions[self.index]
            selected = self.var.get()
            self.finished_count += 1
            was_correct = (selected == q["answer"])
            self.correctness[self.index] = was_correct
            if was_correct:
                self.result_label.config(text="Correct!", fg="green")
                self.score += 1
                self.question_status[self.index].config(bg="green")
            else:
                correct_choice = q["choices"][q["answer"]]
                self.result_label.config(
                    text=f"Incorrect! Correct answer: {q['answer']}) {correct_choice}",
                    fg="red"
                )
                self.question_status[self.index].config(bg="red")

            self.submit_button.config(state="disabled")
            self.next_button.config(state="normal")
            self.save_current_data()  # Save after each answer

    def next_question(self):
        if self.index < self.num_questions - 1:
            self.index += 1
            self.save_current_data()
            self.load_question(self.index)
        else:
            self.show_score()

    def prev_question(self):
        if self.index > 0:
            self.index -= 1
            self.save_current_data()
            self.load_question(self.index)

    def show_score(self):
        messagebox.showinfo(
            "Quiz Complete",
            f"You answered {self.score} out of {len(self.questions)} questions correctly.\n"
            f"You finished {self.finished_count} questions in {PS}."
        )
        self.save_current_data()
        self.master.destroy()

    def save_current_data(self):
        save_session(self.index, self.finished_count, self.correctness)


if __name__ == "__main__":
    start_index, finished_count, correctness = load_session()
    root = tk.Tk()
    app = QuizApp(
        root,
        questions,
        scenario_dict,
        FIGURE_DIR,
        TABLE_DIR,
        start_index=start_index,
        finished_count=finished_count,
        correctness=correctness
    )
    root.mainloop()

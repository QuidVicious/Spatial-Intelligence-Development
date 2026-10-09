import re
import base64
import math
import csv
import os
import tkinter as tk
from tkinter import messagebox, filedialog

def extract_pano_id(url):
    pattern_thumb = r'(?:panoid%3D|panoid=)([A-Za-z0-9_-]+)'
    match = re.search(pattern_thumb, url)
    if match: return match.group(1)

    pattern_data = r'!1s([A-Za-z0-9_-]{22})'
    match_data = re.search(pattern_data, url)
    if match_data:
        short_id = match_data.group(1)
        if short_id.startswith('CIHM'):
            try:
                raw_bytes = b'\x08\x01\x12\x16' + short_id.encode('utf-8')
                long_id = base64.b64encode(raw_bytes).decode('utf-8').replace('=', '')
                return f"CAMSS{long_id}"
            except Exception: return short_id 
        return short_id
    return None

def extract_heading(url):
    yaw_pattern = r'(?:yaw%3D|yaw=)([0-9.]+)'
    yaw_match = re.search(yaw_pattern, url)
    if yaw_match: return float(yaw_match.group(1))
    
    viewport_pattern = r',([0-9.]+)h'
    viewport_match = re.search(viewport_pattern, url)
    if viewport_match: return float(viewport_match.group(1))
    return None

def calculate_focal_length(url):
    fov_pattern = r',([0-9.]+)y'
    match = re.search(fov_pattern, url)
    if match:
        fov = float(match.group(1))
        if 0 < fov < 180:
            sensor_width = 36
            focal_length = sensor_width / (2 * math.tan(math.radians(fov / 2)))
            return fov, round(focal_length, 2)
    return None, None

def extract_coordinates(url):
    coord_pattern = r'(?:@|ll=)(-?\d+\.\d+),(-?\d+\.\d+)'
    match = re.search(coord_pattern, url)
    if match: return float(match.group(1)), float(match.group(2))
    return None, None

class MapExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Forensic Maps Spatial Extractor")
        self.root.geometry("550x500")
        self.root.resizable(True, True)

        # UI Styling Elements
        padding_opts = {'padx': 10, 'pady': 5}

        # URL Input Label & Entry
        tk.Label(root, text="Paste Google Maps URL:", font=('Arial', 10, 'bold')).pack(**padding_opts)
        self.url_entry = tk.Entry(root, width=60)
        self.url_entry.pack(pady=2)
        self.url_entry.bind("<KeyRelease>", self.auto_process) # Automatically extract on paste!

        # Checkbox Framework Frame
        tk.Label(root, text="Select Data Fields to Filter/Extract:", font=('Arial', 10, 'bold')).pack(pady=(10,2))
        chk_frame = tk.Frame(root)
        chk_frame.pack()

        # Variables for checkboxes
        self.chk_pano = tk.BooleanVar(value=True)
        self.chk_heading = tk.BooleanVar(value=True)
        self.chk_fov = tk.BooleanVar(value=True)
        self.chk_coords = tk.BooleanVar(value=True)

        tk.Checkbutton(chk_frame, text="Pano ID", variable=self.chk_pano, command=self.update_display).grid(row=0, column=0, padx=10)
        tk.Checkbutton(chk_frame, text="Heading", variable=self.chk_heading, command=self.update_display).grid(row=0, column=1, padx=10)
        tk.Checkbutton(chk_frame, text="FOV / Lens", variable=self.chk_fov, command=self.update_display).grid(row=0, column=2, padx=10)
        tk.Checkbutton(chk_frame, text="Coordinates", variable=self.chk_coords, command=self.update_display).grid(row=0, column=3, padx=10)

        # Output Results Window
        tk.Label(root, text="Extracted Live Data Output:", font=('Arial', 10, 'bold')).pack(pady=(10,2))
        self.output_text = tk.Text(root, height=12, width=65, bg="#f0f0f0", font=('Courier', 10))
        self.output_text.pack(**padding_opts)

        # Action Buttons Layout Frame
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Clear Form", command=self.clear_fields, width=15).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="Write to CSV File", command=self.save_to_csv, bg="#4CAF50", fg="white", font=('Arial', 10, 'bold'), width=20).grid(row=0, column=1, padx=5)

        # Cache memory holding latest scan data
        self.latest_data = {}

    def auto_process(self, event=None):
        url = self.url_entry.get().strip()
        if not url:
            self.clear_display()
            return

        # Core Parsing Engine Execution
        pano = extract_pano_id(url)
        heading = extract_heading(url)
        fov, focal = calculate_focal_length(url)
        lat, lng = extract_coordinates(url)

        # Save all results to active memory cache
        self.latest_data = {
            'url': url, 'pano': pano, 'heading': heading,
            'fov': fov, 'focal': focal, 'lat': lat, 'lng': lng
        }
        self.update_display()

    def update_display(self):
        self.output_text.config(state=tk.NORMAL)
        self.clear_display()

        if not self.latest_data:
            self.output_text.config(state=tk.DISABLED)
            return

        d = self.latest_data
        has_printed = False

        if self.chk_pano.get():
            self.output_text.insert(tk.END, f"Panorama ID:    {d['pano'] if d['pano'] else 'Not Found'}\n")
            has_printed = True
        if self.chk_heading.get():
            val = f"{d['heading']}°" if d['heading'] is not None else 'Not Found'
            self.output_text.insert(tk.END, f"Compass Heading:{val}\n")
            has_printed = True
        if self.chk_fov.get():
            fov_val = f"{d['fov']}°" if d['fov'] is not None else 'Not Found'
            focal_val = f"{d['focal']}mm" if d['focal'] is not None else 'Not Found'
            self.output_text.insert(tk.END, f"Field of View:  {fov_val}\n")
            self.output_text.insert(tk.END, f"Lens Dynamic:   {focal_val} (Full-Frame Equiv.)\n")
            has_printed = True
        if self.chk_coords.get():
            coord_val = f"{d['lat']}, {d['lng']}" if d['lat'] is not None else 'Not Found'
            self.output_text.insert(tk.END, f"GPS Coordinates:{coord_val}\n")
            has_printed = True

        if not has_printed:
            self.output_text.insert(tk.END, "[No data boxes checked to display metrics]")

        self.output_text.config(state=tk.DISABLED)

    def save_to_csv(self):
        if not self.latest_data:
            messagebox.showerror("Error", "No extracted data present to save. Please paste a valid URL first.")
            return

        # Prompt user to choose where to save file
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile="extracted_maps_data.csv"
        )
        if not filename: return # Cancelled operation

        file_exists = os.path.isfile(filename)
        
        # Build headers dynamically based on checked filters
        headers, row = ["Source URL"], [self.latest_data['url']]
        d = self.latest_data

        if self.chk_pano.get():
            headers.append("Pano ID"); row.append(d['pano'] or "N/A")
        if self.chk_heading.get():
            headers.append("Heading (Deg)"); row.append(d['heading'] if d['heading'] is not None else "N/A")
        if self.chk_fov.get():
            headers.extend(["FOV", "Focal Length (mm)"])
            row.extend([d['fov'] if d['fov'] is not None else "N/A", d['focal'] if d['focal'] is not None else "N/A"])
        if self.chk_coords.get():
            headers.extend(["Latitude", "Longitude"])
            row.extend([d['lat'] if d['lat'] is not None else "N/A", d['lng'] if d['lng'] is not None else "N/A"])

        try:
            with open(filename, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists or os.stat(filename).st_size == 0:
                    writer.writerow(headers)
                writer.writerow(row)
            messagebox.showinfo("Success", f"Data safely appended to:\n{filename}")
        except Exception as e:
            messagebox.showerror("File Error", f"Could not write to file. Is it open somewhere else?\nDetails: {e}")

    def clear_display(self):
        self.output_text.delete('1.0', tk.END)

    def clear_fields(self):
        self.url_entry.delete(0, tk.END)
        self.latest_data = {}
        self.output_text.config(state=tk.NORMAL)
        self.clear_display()
        self.output_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = MapExtractorApp(root)
    root.mainloop()

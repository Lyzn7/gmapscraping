import customtkinter as ctk
import pandas as pd
from tkinter import ttk, messagebox
import threading
import requests
from io import BytesIO
from PIL import Image
import os
import urllib.request
from scraper import GMapScraper

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LYZN - Google Maps Scraper Pro")
        self.geometry("1300x700")

        self.scraper = GMapScraper()
        self.scraping_thread = None
        self.data_df = pd.DataFrame(columns=[
            "Nama Tempat", "Alamat", "Nomor HP", "Website", "Rating", "Jumlah Ulasan", "Link Map", "Image URL"
        ])

        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=3) # left
        self.grid_columnconfigure(1, weight=1) # right
        self.grid_rowconfigure(1, weight=1)

        # Top Frame for Inputs
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.grid(row=0, column=0, columnspan=2, pady=10, padx=10, sticky="ew")

        self.keyword_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Keyword (e.g., Cafe)", width=200)
        self.keyword_entry.pack(side="left", padx=5)

        self.location_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Location (e.g., Jakarta)", width=200)
        self.location_entry.pack(side="left", padx=5)

        self.start_btn = ctk.CTkButton(self.top_frame, text="Start Scraping", command=self.start_scraping, fg_color="green")
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn = ctk.CTkButton(self.top_frame, text="Stop", command=self.stop_scraping, fg_color="red", state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        self.export_btn = ctk.CTkButton(self.top_frame, text="Export CSV", command=self.export_csv)
        self.export_btn.pack(side="left", padx=5)

        # Left frame for Treeview
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=1, column=0, pady=5, padx=(10,5), sticky="nsew")

        columns = ("Nama Tempat", "Alamat", "Nomor HP", "Website", "Rating", "Jumlah Ulasan", "Link Map", "Image URL")
        
        tree_scroll_y = ttk.Scrollbar(self.left_frame)
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x = ttk.Scrollbar(self.left_frame, orient="horizontal")
        tree_scroll_x.pack(side="bottom", fill="x")
        
        self.tree = ttk.Treeview(self.left_frame, columns=columns, show="headings", 
                                 yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        self.tree.pack(fill="both", expand=True)
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Right Frame for Images (Detail Panel)
        self.right_frame = ctk.CTkScrollableFrame(self, label_text="Tinjauan Gambar")
        self.right_frame.grid(row=1, column=1, pady=5, padx=(5,10), sticky="nsew")
        
        # Bottom Frame for Status
        self.bottom_frame = ctk.CTkFrame(self)
        self.bottom_frame.grid(row=2, column=0, columnspan=2, pady=(0,10), padx=10, sticky="ew")

        self.status_label = ctk.CTkLabel(self.bottom_frame, text="Status: Ready")
        self.status_label.pack(side="left", padx=5)
        
        self.brand_label = ctk.CTkLabel(self.bottom_frame, text="Powered by LYZN", text_color="gray", font=("Arial", 12, "bold"))
        self.brand_label.pack(side="right", padx=10)

    def start_scraping(self):
        keyword = self.keyword_entry.get()
        location = self.location_entry.get()
        if not keyword:
            messagebox.showerror("Error", "Please enter a keyword")
            return
        
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="Status: Scraping started...")
        
        self.scraping_thread = threading.Thread(target=self.scraper.start, args=(keyword, location, self.on_data_found, self.on_task_finished))
        self.scraping_thread.start()

    def stop_scraping(self):
        self.status_label.configure(text="Status: Stopping...")
        self.scraper.stop()

    def export_csv(self):
        if self.data_df.empty:
            messagebox.showinfo("Info", "No data to export.")
            return
            
        home_dir = os.path.expanduser("~")
        download_dir = os.path.join(home_dir, "Downloads")
        
        filepath = ctk.filedialog.asksaveasfilename(
            initialdir=download_dir,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Data as CSV",
            initialfile="gmaps_data.csv"
        )
        
        if filepath:
            self.data_df.to_csv(filepath, index=False)
            messagebox.showinfo("Success", f"Data exported to {filepath}")

    def on_data_found(self, data):
        self.tree.insert("", "end", values=(
            data.get("Nama Tempat"), data.get("Alamat"), data.get("Nomor HP"),
            data.get("Website"), data.get("Rating"), data.get("Jumlah Ulasan"),
            data.get("Link Map"), data.get("Image URL")
        ))
        self.data_df.loc[len(self.data_df)] = data

        count = len(self.tree.get_children())
        self.status_label.configure(text=f"Status: Scraped {count} items")
        try:
            self.data_df.to_csv("gmaps_data_autosave.csv", index=False)
        except:
            pass

    def on_task_finished(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="Status: Scraping finished.")
        
    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
            
        item = self.tree.item(selected[0])
        values = item["values"]
        image_urls_str = values[7]
        
        # Clear existing image widgets
        for widget in self.right_frame.winfo_children():
            widget.destroy()
            
        ctk.CTkLabel(self.right_frame, text=f"Tempat:\n{values[0]}", font=("Arial", 14, "bold"), wraplength=250).pack(pady=10)
            
        if not image_urls_str or image_urls_str == "-":
            ctk.CTkLabel(self.right_frame, text="Tidak ada gambar ditemukan.").pack(pady=10)
            return
            
        urls = image_urls_str.split("|")
        urls = urls[:5]
        
        threading.Thread(target=self.load_images_to_panel, args=(urls,)).start()
        
    def load_images_to_panel(self, urls):
        for idx, url in enumerate(urls):
            try:
                if not url.startswith("http"): continue
                response = requests.get(url, timeout=5)
                img = Image.open(BytesIO(response.content))
                # Pass PIL image to main thread, otherwise CTkImage inside non-main thread crashes
                self.after(0, self.add_image_widget, img, url, idx+1)
            except Exception as e:
                print(f"Failed to load image {url}: {e}")
                
    def add_image_widget(self, img, url, num):
        container = ctk.CTkFrame(self.right_frame)
        container.pack(pady=10, padx=5, fill="x")
        
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(250, 200))
        lbl = ctk.CTkLabel(container, image=ctk_img, text="")
        lbl.pack(pady=5)
        
        btn = ctk.CTkButton(container, text=f"Unduh Gambar {num}", fg_color="blue", width=120, command=lambda u=url, n=num: self.download_image(u, n))
        btn.pack(pady=5)
        
    def download_image(self, url, num):
        home_dir = os.path.expanduser("~")
        download_dir = os.path.join(home_dir, "Downloads")
        
        filepath = ctk.filedialog.asksaveasfilename(
            initialdir=download_dir,
            defaultextension=".jpg",
            filetypes=[("JPEG files", "*.jpg"), ("PNG files", "*.png"), ("All files", "*.*")],
            title="Save Image",
            initialfile=f"place_image_{num}.jpg"
        )
        if filepath:
            try:
                urllib.request.urlretrieve(url, filepath)
                messagebox.showinfo("Success", f"Image saved to {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {e}")

if __name__ == "__main__":
    app = App()
    app.mainloop()

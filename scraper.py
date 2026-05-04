import time
import random
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from urllib.parse import quote

class GMapScraper:
    def __init__(self):
        self.driver = None
        self.is_running = False

    def init_driver(self):
        options = webdriver.EdgeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1280,800")
        options.add_argument("--lang=id")

        self.driver = webdriver.Edge(options=options)
        self.wait = WebDriverWait(self.driver, 15)

    def random_delay(self, min_sec=1, max_sec=3):
        time.sleep(random.uniform(min_sec, max_sec))
        
    def to_stars(self, rating_str):
        try:
            val = float(rating_str.replace(',', '.'))
            full = int(val)
            half = 1 if val - full >= 0.3 else 0
            empty = 5 - full - half
            return ('⭐' * full) + ('½' * half) + ('☆' * empty) + f" ({rating_str})"
        except:
            return rating_str

    def start(self, keyword, location, on_data_cb, on_finished_cb):
        self.is_running = True
        try:
            self.init_driver()
            query = f"{keyword} di {location}" if location else keyword
            search_url = f"https://www.google.com/maps/search/{quote(query)}"
            self.driver.get(search_url)
            
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/maps/place/']")))
            except TimeoutException:
                print("Timeout waiting for results.")
                return

            self.scroll_and_extract(on_data_cb)
            
        except Exception as e:
            print(f"Error during scraping: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
            self.is_running = False
            on_finished_cb()

    def scroll_and_extract(self, on_data_cb):
        processed_urls = set()
        
        while self.is_running:
            links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']")
            new_elements_found = False
            
            for link in links:
                if not self.is_running:
                    break
                    
                url = link.get_attribute("href")
                if url in processed_urls or not url:
                    continue
                    
                new_elements_found = True
                processed_urls.add(url)
                
                try:
                    aria_label = link.get_attribute("aria-label")
                    name = aria_label if aria_label else "Unknown"
                    
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
                    self.random_delay(0.5, 1.5)
                    
                    self.driver.execute_script("arguments[0].click();", link)
                    self.random_delay(2, 4) 
                    
                    data = self.extract_details(name, url)
                    if data:
                        on_data_cb(data)
                        
                except Exception as e:
                    print(f"Error parsing item: {e}")
                    
            try:
                scrollable_div = self.driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
                self.driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", scrollable_div)
            except NoSuchElementException:
                self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_DOWN)
                
            self.random_delay(2, 4)
            
            page_text = self.driver.page_source
            if "telah mencapai akhir daftar" in page_text.lower() or "reached the end of the list" in page_text.lower():
                print("Reached the end of list.")
                break
                
            if not new_elements_found:
                self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_DOWN)
                self.random_delay(2, 3)
                links_after = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']")
                urls_after = set([l.get_attribute("href") for l in links_after])
                if urls_after.issubset(processed_urls):
                    print("No new elements found, breaking loop.")
                    break

    def extract_details(self, fallback_name, url):
        data = {
            "Nama Tempat": fallback_name,
            "Alamat": "-",
            "Nomor HP": "-",
            "Website": "-",
            "Rating": "-",
            "Jumlah Ulasan": "-",
            "Link Map": url,
            "Image URL": "-"
        }
        
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1")))
            
            try:
                data["Nama Tempat"] = self.driver.find_element(By.CSS_SELECTOR, "h1.DUwDvf").text
            except:
                try:
                    data["Nama Tempat"] = self.driver.find_element(By.CSS_SELECTOR, "h1").text
                except:
                    pass
                
            try:
                # Based on user payload: <div class="F7nice"><span>4.5</span>...</div>
                rating_elem = self.driver.find_element(By.CSS_SELECTOR, "div.F7nice > span")
                data["Rating"] = self.to_stars(rating_elem.text)
            except:
                pass

            try:
                review_elem = self.driver.find_element(By.CSS_SELECTOR, "span[role='img'][aria-label*='review'], span[role='img'][aria-label*='ulasan']")
                data["Jumlah Ulasan"] = review_elem.text.strip('()')
            except:
                try:
                    review_elem = self.driver.find_element(By.XPATH, "//button[contains(@aria-label, 'ulasan') or contains(@aria-label, 'reviews')]")
                    data["Jumlah Ulasan"] = review_elem.text.strip('()')
                except:
                    pass
                
            try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[data-item-id]")
                for btn in buttons:
                    item_id = btn.get_attribute("data-item-id")
                    if "address" in item_id:
                        lbl = btn.get_attribute("aria-label") or ""
                        data["Alamat"] = lbl.replace("Alamat: ", "").replace("Address: ", "").strip()
                    elif "phone" in item_id:
                        lbl = btn.get_attribute("aria-label") or ""
                        if ":" in lbl:
                            data["Nomor HP"] = lbl.split(":", 1)[-1].strip()
                        else:
                            # fallback for exact text to avoid label weirdness
                            data["Nomor HP"] = btn.text.strip()
                    elif "authority" in item_id:
                        lbl = btn.get_attribute("aria-label") or ""
                        data["Website"] = lbl.replace("Situs web: ", "").replace("Website: ", "").strip()
            except:
                pass
                
            try:
                images = []
                img_elems = self.driver.find_elements(By.CSS_SELECTOR, "img.DaSXdd")
                if not img_elems:
                    img_elems = self.driver.find_elements(By.CSS_SELECTOR, "img[decoding='async']")
                    
                for img in img_elems:
                    src = img.get_attribute("src")
                    # Check if valid image
                    if src and ("googleusercontent" in src or "ggpht" in src) and src not in images:
                        images.append(src)
                    if len(images) == 5:
                        break
                        
                if not images:
                    data["Image URL"] = "-"
                else:
                    data["Image URL"] = "|".join(images)
            except:
                pass
                
            return data
        except Exception as e:
            print(f"Failed to extract details: {e}")
            return data

    def stop(self):
        self.is_running = False

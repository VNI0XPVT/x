import os
from typing import List

import yaml

languages = {}
languages_present = {}


def get_string(lang: str):
    return languages[lang]


# Use absolute path for strings directory to avoid path issues
strings_dir = os.path.join(os.path.dirname(__file__), "langs")

try:
    for filename in os.listdir(strings_dir):
        if "en" not in languages:
            en_path = os.path.join(strings_dir, "en.yml")
            if os.path.exists(en_path):
                with open(en_path, encoding="utf8") as f:
                    languages["en"] = yaml.safe_load(f)
                languages_present["en"] = languages["en"]["name"]
        
        if filename.endswith(".yml"):
            language_name = filename[:-4]
            if language_name == "en":
                continue
                
            lang_path = os.path.join(strings_dir, filename)
            if os.path.exists(lang_path):
                with open(lang_path, encoding="utf8") as f:
                    languages[language_name] = yaml.safe_load(f)
                    
                for item in languages["en"]:
                    if item not in languages[language_name]:
                        languages[language_name][item] = languages["en"][item]
        
        try:
            languages_present[language_name] = languages[language_name]["name"]
        except:
            print(f"Issue with language file: {filename}")
            continue

except Exception as e:
    print(f"Error loading language files: {e}")
    # Fallback - create minimal English language support
    if "en" not in languages:
        languages["en"] = {"name": "English"}
        languages_present["en"] = "English"

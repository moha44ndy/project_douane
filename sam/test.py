import requests
import json

from_code = "en"
to_code = "fr"

def traduire_texte_avec_argos(text, source_lang, target_lang):
    url = "https://libretranslate.com/translate"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "q": text,
        "source": source_lang,
        "target": target_lang
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    if response.status_code == 200:
        resultats = response.json()
        return resultats.get("translatedText", "")
    else:
        print(f"Erreur: {response.status_code}")
        return None

texte_source = "Hello!"
texte_traduit = traduire_texte_avec_argos(texte_source, "en", "es")
print(texte_traduit)  # Devrait afficher: "¡Hola!"

import argostranslate.package

model_path = "/home/wabi-lat/.local/cache/argos-translate/downloads/translate-en_fr.argosmodel"

argostranslate.package.install_from_path(model_path)

print("Modèles installés :", argostranslate.package.get_installed_packages())

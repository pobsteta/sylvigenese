"""Modules Python de sylvigenese : import_tarif, post, assets (spec §2).

Squelette de la mission 012 : chaque module lit config.yml et fait valider ce fichier.
Les trois modules ne s'importent pas entre eux ; ils partagent seulement `common`
(lecture de la config, appel du validateur), qui n'a aucune logique métier.
"""

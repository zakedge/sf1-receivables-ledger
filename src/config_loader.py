import json


def load_config(config_file_path="config/settings.json"):
    """
    Load application configuration from JSON file.
    """

    with open(config_file_path, "r") as file:
        config = json.load(file)

    return config
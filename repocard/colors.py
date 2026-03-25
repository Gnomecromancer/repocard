"""GitHub linguist language colors (hex strings, no #)."""

LANG_COLORS: dict[str, str] = {
    "Python":        "3572A5",
    "JavaScript":    "f1e05a",
    "TypeScript":    "2b7489",
    "Rust":          "dea584",
    "Go":            "00ADD8",
    "Java":          "b07219",
    "C":             "555555",
    "C++":           "f34b7d",
    "C#":            "178600",
    "Ruby":          "701516",
    "PHP":           "4F5D95",
    "Swift":         "ffac45",
    "Kotlin":        "A97BFF",
    "Scala":         "c22d40",
    "Shell":         "89e051",
    "PowerShell":    "012456",
    "HTML":          "e34c26",
    "CSS":           "563d7c",
    "SCSS":          "c6538c",
    "Vue":           "2c3e50",
    "Svelte":        "ff3e00",
    "Dart":          "00B4AB",
    "Lua":           "000080",
    "Haskell":       "5e5086",
    "OCaml":         "3be133",
    "Elixir":        "6e4a7e",
    "Clojure":       "db5855",
    "Julia":         "a270ba",
    "R":             "198CE7",
    "Jupyter Notebook": "DA5B0B",
    "Makefile":      "427819",
    "Dockerfile":    "384d54",
    "YAML":          "cb171e",
    "TOML":          "9c4221",
}

DEFAULT_COLOR = "6e7681"


def lang_color(lang: str) -> str:
    return LANG_COLORS.get(lang, DEFAULT_COLOR)

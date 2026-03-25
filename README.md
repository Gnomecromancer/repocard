# repocard

Generate SVG stat cards for GitHub repos. Drop one in your README.

```
pip install repocard
repocard generate torvalds/linux
```

No auth needed for public repos (uses GitHub's public API, 60 req/hr).

## Usage

```
repocard generate OWNER/REPO [--output card.svg]
```

## Example

```
repocard generate psf/requests --output requests.svg
```

## PNG output

```
pip install repocard[png]
repocard generate owner/repo --png
```

Requires `cairosvg` (and cairo system library).

## License

MIT

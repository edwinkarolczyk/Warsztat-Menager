# Data directory structure

This document describes how the application stores domain data under the `data/` directory. All JSON files are encoded in UTF-8 and formatted with two-space indentation, as noted in [AGENTS.md](../AGENTS.md).

## `data/produkty/`
Each product is stored as its own JSON file representing a bill of materials (BOM).

Example:

```json
{
  "kod": "PRD001",
  "nazwa": "Stojak spawany",
  "version": "1.0",
  "bom_revision": 1,
  "polprodukty": [
    {
      "kod": "PP001",
      "ilosc_na_szt": 2.0,
      "surowiec": {
        "typ": "SR001",
        "dlugosc": 0.2
      }
    }
  ]
}
```

## `data/polprodukty.json`
Stock levels for semi-finished goods are tracked in `data/magazyn/polprodukty.json`. The file maps each code to its quantity and unit.

Example:

```json
{
  "PP001": {
    "stan": 50.0,
    "jednostka": "szt"
  },
  "PP002": {
    "stan": 12.0,
    "jednostka": "szt"
  }
}
```

## `data/magazyn/`
Warehouse data is organised in this directory:

- `stany.json` – map of raw material codes to their stock and alert thresholds.
- `przyjecia.json` – list of incoming deliveries.
- `surowce.json` – array of raw material definitions.
- `magazyn.json` – aggregated view of items with metadata.
- `polprodukty.json` – semi-finished product stock levels (as above).

Example `stany.json` snippet:

```json
{
  "RURKA_30": {
    "nazwa": "Rurka 30mm",
    "stan": 21,
    "prog_alert": 5
  }
}
```

Example `surowce.json` entry:

```json
{
  "kod": "SR001",
  "nazwa": "Blacha stalowa 2mm",
  "rodzaj": "blacha",
  "rozmiar": "100x200",
  "dlugosc": 200,
  "jednostka": "mb",
  "stan": 100,
  "prog_alertu": 10
}
```

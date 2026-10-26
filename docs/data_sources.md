# Data sources and attribution

All nutrition data in Venn is bundled in the repository and used offline. The app never calls an external food API.

| File | Source | Licence | Contents |
|---|---|---|---|
| `backend/app/data/usda_sr_legacy.json.gz` | USDA FoodData Central, **SR Legacy** (April 2018 release), downloaded 2026-10-25 from https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip | Public domain (U.S. Government work) | 7,793 generic foods. Energy (nutrient 1008), protein (1003), carbohydrate by difference (1005) and total fat (1004), per 100 g. Also USDA household portions with gram weights (7,533 foods have at least one). |
| `backend/app/data/usda_branded_sample.json` | USDA FoodData Central, **Branded Foods** (April 2026 release), downloaded 2026-10-25 from https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_branded_food_csv_2026-04-30.zip | Public domain | 20 packaged US products, each with its GTIN/UPC barcode and label serving. Nutrients are as FDC publishes them: label data supplied by manufacturers (via GS1 / Label Insight) and normalised by FDC to per 100 g or per 100 ml. |
| `backend/app/data/exercises.json` | **free-exercise-db** by yuhonas (https://github.com/yuhonas/free-exercise-db), `dist/exercises.json`, downloaded 2026-10-24 | The Unlicense (public domain) | 80 curated exercises: name, equipment, level, mechanic, muscles, and the first two instruction steps. Venn's own curation tags (pattern, extra equipment, reps or time, unilateral, loaded body areas) are added by `scripts/build_exercise_catalog.py`. |
| `backend/app/data/staple_foods.json` | Venn (curated) | n/a | 67 names of everyday SR Legacy foods. They only boost search ranking (e.g. "Egg, whole, raw, fresh" ranks above "Egg, whole, dried"). No nutrition values. |

## How the files were built

`scripts/build_food_catalog.py` builds the files from the original downloads:

```bash
python scripts/build_food_catalog.py sr-legacy path/to/FoodData_Central_sr_legacy_food_csv_2018-04.zip
```

```bash
python scripts/build_food_catalog.py branded-bulk path/to/FoodData_Central_branded_food_csv_2026-04-30.zip
```

- **Completeness:** a food is kept only if it has all four core values. No value is estimated or filled in. (For SR Legacy, no foods were dropped.)
- **Branded products:** products are picked from a fixed list of brand and product pairs (e.g. Quest protein bars, Fairlife milk, Cheerios). The script keeps up to two current US products per pair. It skips discontinued items, servings not in g or ml, and barcodes with an invalid check digit. Twenty products matched.
- **API fallback:** the FoodData Central search API with `DEMO_KEY` was tried first, but it is limited to about 10 requests per hour and returned HTTP 429. The bulk file was used instead. The `branded` command, which uses the API, remains available.

## Known data limitations

- **Release date:** SR Legacy is the final 2018 release; USDA no longer updates it. Newer USDA datasets (Foundation Foods, FNDDS) are not included yet.
- **Branded values:** these are what manufacturers reported. Venn does not check them against the package. Products may have been reformulated since they were published.
- **Coverage:** only the 20 bundled products can be found by barcode. Any other code gets a clear "not in the offline sample" message, with search and manual entry offered instead.
- **Liquids:** Branded Foods reports liquid products per 100 ml. Venn keeps them in ml and does not convert between volume and weight.

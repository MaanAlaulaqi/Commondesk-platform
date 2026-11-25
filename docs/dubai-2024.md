# DubaiV2Example

The local release contains 2,500 Bangkok Traffy Fondue submissions with initial photographs. The original report date determines eligibility. A fixed random sample gives each month of 2024 either 208 or 209 submissions. The sampler selects Thai complaints 6–160 characters long and excludes repeated source IDs and exact prepared-photo hashes. Different residents may use the same wording, and different photographs may depict the same incident.

Each case keeps its original Thai complaint and source reference. The release stores four machine translations under the same case ID. The map uses six representative Dubai neighborhood points from the earlier example and a repeatable offset derived from the case ID. The source calendar day is real. The time of day, workflow and Dubai pin are illustrative. Urgency suggestions are unreviewed. The media manifest retains the digest of the source JPEG and the displayed WebP.

## Build from the private source

The commands below use the project's prepared initial-photo Parquet archive, its catalog, the earlier seed's neighborhood file, the local NLLB-200 distilled 600M CTranslate2 model, and the retrieval kit containing the pinned E5 and DINOv2 encoders. Set the paths to those local inputs. Preparation requires PyArrow and Pillow, translation requires CTranslate2 and SentencePiece, and indexing uses the retrieval kit's Python dependencies.

```sh
root=.data/DubaiV2Example
python scripts/prepare_dubai_2024.py "$catalog" "$shards" "$places" "$root"
python scripts/translate_dubai_2024.py "$root" "$nllb"
python scripts/package_dubai_2024.py "$root"
python scripts/build_dubai_2024_vectors.py "$root" "$kit" photo
python scripts/build_dubai_2024_vectors.py "$root" "$kit" text
```

The translator resumes completed batches from SQLite. The local release includes a small `translation-edits.json` file with corrections made during spot checks. Keep that file alongside the source pairs to reproduce the packaged wording. Text lookup uses multilingual E5 over all five language versions. Common short queries such as “sidewalk”, “رصيف” and “ทางเท้า” share a multilingual topic vector. A longer query retains the meaning of the full sentence. Matching a topic never restricts candidate reports to a category or language. Results display the stored wording for the interface language, or the explicitly selected language filter. Case detail retains the Thai original. Photo lookup uses DINOv2 over the attached photographs. The worker deduplicates by case ID before returning results. Search shows 50 cases per numbered page and reuses the submitted query when paging. The total counts eligible indexed cases ranked by similarity. The source key is `dubai2024` and its dedicated vector alias is `commondesk_dubai_example_2024`.

## Load the local release

With the Compose stack running on this revision, run `./scripts/import-dubai-2024`. The script loads the vector collection and case store using the pinned release checksums. Repeating it preserves case reviews. The private media, generated translations, and vector files live under the ignored `.data` directory. A newly generated release with different artifacts needs its checksums updated in the two seed importers.

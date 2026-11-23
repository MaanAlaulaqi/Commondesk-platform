# Internal translation evaluation

The attested split and evaluation rules are in `receipt/` and `protocol.md`. Each ordered pair has 25 training incidents, five development incidents and five held-out incidents. These are invented, model-authored cases. All versions of an incident come from the same set of five texts and must remain together.

The private run directory `.data/mt-pilot/` holds the original multilingual rows, expanded splits, model predictions and ballots. Its source format is newline-delimited with seven pipe-separated fields in this order: incident ID, split, English, Thai, Arabic, Hindi and Urdu. The one-time freeze expands rows, records SHA-256 hashes and signs the manifest. Reuse the existing freeze to reproduce the run.

Verify the archived signature and protocol from the repository root.

```sh
ssh-keygen -Y verify -I pilot -n commondesk-mt \
  -f translator_pilot/data/receipt/allowed_signers \
  -s translator_pilot/data/receipt/freeze.json.sig < translator_pilot/data/receipt/freeze.json
sha256sum translator_pilot/data/protocol.md
```

Create the two independent private packet directories after obtaining both sets of held-out predictions.

```sh
python translator_pilot/data/judging.py create .data/mt-pilot \
  .data/mt-pilot/results/frozen_test.jsonl .data/mt-pilot/results/adapter_test.jsonl \
  .data/mt-pilot/judges
```

Give each reader only its own packet and instructions. Identify each reader's model and version in the run record. Save each completed ballot next to its packet. Summarize the paired judgments.

```sh
python translator_pilot/data/judging.py tally \
  .data/mt-pilot/judges/private-key.jsonl \
  .data/mt-pilot/judges/a/ballot.jsonl .data/mt-pilot/judges/b/ballot.jsonl \
  > .data/mt-pilot/judges/tally.json
```

The run also provides an automated synthetic-only dispatcher. Run `python translator_pilot/data/readers.py .data/mt-pilot --preflight` to validate the two isolated reader sessions on invented controls. For the actual frozen outputs run `python translator_pilot/data/readers.py .data/mt-pilot`. It creates fresh randomized IDs and ordering, sends batches of 25 to each process over stdin, validates exact ID coverage, and records reader identifiers alongside the private aggregate. It resumes completed batch files during recovery. The per-direction negative tag counts count reader votes, so two readers may tag the same translation.

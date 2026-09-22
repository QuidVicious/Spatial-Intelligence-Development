# LSA Dispatcher

Local, SI-only dispatch to the image model. Every run is logged in full and every batch gets a contact sheet.

## Setup (once)

    conda activate depth_env
    cd C:\DEV\Squid\SquidBlack\Spatial-Intelligence-Development-Base\Dual-Pipeline\lsa\lsa-dispatcher
    pip install -r requirements.txt

1. System instructions live in the shared library `lsa\si\`, one level up (set by `si_dir` in config.json).
   Every .md or .txt there appears in the menu. A changed SI gets a new version number; never edit one in place,
   or old run logs will carry a hash that matches no file.
2. Check `config.json`:
   - `model`: confirm the exact model ID against AI Studio's "Get code" for Nano Banana 2.
   - `api_key_env_names`: must include the variable name used in your .env. The server searches upward from this folder for the nearest .env.

## Run

    conda activate depth_env
    python server.py

Open http://127.0.0.1:5057

## What gets written

    runs\<batch_id>\batch.json        full record: settings, SI hash, every run's prompt, text, thoughts, seed, model version, timing, review
    runs\<batch_id>\si_snapshot.txt   exact SI text used for the batch
    runs\<batch_id>\rNN_<value>.png   images
    runs\<batch_id>\contact_sheet.jpg regenerated whenever you select or tag frames
    runs\log.jsonl                    one line per run across all batches

## Sweeps

Put `{sweep}` in the prompt and list values one per line. Each value runs "Runs per value" times.
Seed: blank for none; a number counts up per run unless "Same seed for every run" is checked.

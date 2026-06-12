"""
Auto Insurance Risk Data Pipeline
==================================
Orchestrates: Ingest → Normalize → Score → Report

Usage:
    python run_pipeline.py                        # uses default paths
    python run_pipeline.py --raw data/raw         # custom raw data dir
    python run_pipeline.py --out reports          # custom output dir
"""
import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.ingest import ingest
from pipeline.normalize import normalize
from pipeline.score import score
from pipeline.report import report
from pipeline.fremtpl2 import normalize_fremtpl2, score_fremtpl2, report_fremtpl2


def run(raw_dir: str = "data/raw", output_dir: str = "reports") -> None:
    logger.info(" STAGE 1: INGEST")
    sources = ingest(raw_dir)
    if not sources:
        logger.error("No source data found. Run: python data/generate_sample_data.py")
        sys.exit(1)

    if "freMTPL2freq" in sources:
        logger.info(" STAGE 2: NORMALIZE (freMTPL2freq) ")
        merged = normalize_fremtpl2(sources["freMTPL2freq"])

        logger.info(" STAGE 3: RISK SCORING (freMTPL2freq) ")
        scored = score_fremtpl2(merged)

        logger.info(" STAGE 4: REPORT (freMTPL2freq) ")
        report_fremtpl2(scored, output_dir)
    else:
        logger.info(" STAGE 2: NORMALIZE ")
        merged = normalize(sources)

        logger.info(" STAGE 3: RISK SCORING ")
        scored = score(merged)

        logger.info(" STAGE 4: REPORT ")
        report(scored, output_dir)

    logger.info("Pipeline complete. Check output directory for results.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Insurance Risk Pipeline")
    parser.add_argument("--raw", default="data/raw", help="Raw data directory")
    parser.add_argument("--out", default="reports", help="Output directory")
    args = parser.parse_args()
    run(raw_dir=args.raw, output_dir=args.out)

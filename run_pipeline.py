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

    def _dispatch_pipeline(sources_dict, out_dir: str):
        if "freMTPL2freq" in sources_dict:
            logger.info(" STAGE 2: NORMALIZE (freMTPL2freq) ")
            merged_local = normalize_fremtpl2(sources_dict["freMTPL2freq"])

            logger.info(" STAGE 3: RISK SCORING (freMTPL2freq) ")
            scored_local = score_fremtpl2(merged_local)

            logger.info(" STAGE 4: REPORT (freMTPL2freq) ")
            report_fremtpl2(scored_local, out_dir)
        else:
            logger.info(" STAGE 2: NORMALIZE ")
            merged_local = normalize(sources_dict)

            logger.info(" STAGE 3: RISK SCORING ")
            scored_local = score(merged_local)

            logger.info(" STAGE 4: REPORT ")
            report(scored_local, out_dir)

    _dispatch_pipeline(sources, output_dir)
    logger.info("Pipeline complete. Check output directory for results.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Insurance Risk Pipeline")
    parser.add_argument("--raw", default="data/raw", help="Raw data directory")
    parser.add_argument("--out", default="reports", help="Output directory")
    args = parser.parse_args()
    run(raw_dir=args.raw, output_dir=args.out)

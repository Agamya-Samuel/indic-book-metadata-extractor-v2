import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import preprocessing, ocr_service


def main():
    parser = argparse.ArgumentParser(description="Test OCR preprocessing pipeline")
    parser.add_argument("--image", type=str, help="Path to page image (PNG/JPG)")
    parser.add_argument("--language", type=str, default="tel", choices=["tel", "hin"])
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="JSON string for preprocessing config",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(__file__).parent / "test_output"),
    )
    args = parser.parse_args()

    if not args.image:
        print("Error: --image is required")
        sys.exit(1)

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = {}
    if args.config:
        try:
            config = json.loads(args.config)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON config: {e}")
            sys.exit(1)

    print(f"Input image: {image_path}")
    print(f"Language: {args.language}")
    print(f"Config: {json.dumps({**preprocessing.DEFAULT_PREPROCESSING_CONFIG, **config}, indent=2)}")
    print()

    processed_path = output_dir / f"{image_path.stem}_processed.png"
    print(f"Running preprocessing pipeline...")
    try:
        preprocessing.run_pipeline(image_path, config, processed_path)
        print(f"Processed image saved to: {processed_path}")
    except Exception as e:
        print(f"Preprocessing failed: {e}")
        sys.exit(1)

    print()
    print(f"Running OCR on processed image...")
    try:
        ocr_data = ocr_service.run_ocr(processed_path, args.language)
    except Exception as e:
        print(f"OCR failed on processed image: {e}")
        print()
        print(f"Trying OCR on original image...")
        try:
            ocr_data = ocr_service.run_ocr(image_path, args.language)
        except Exception as e2:
            print(f"OCR also failed on original: {e2}")
            sys.exit(1)

    print()
    print("=" * 60)
    print("OCR RESULTS")
    print("=" * 60)
    print(f"Word count: {ocr_data['word_count']}")
    print(f"Average confidence: {ocr_data['avg_confidence']}%")
    print()
    print("EXTRACTED TEXT:")
    print("-" * 60)
    print(ocr_data["full_text"])
    print("-" * 60)

    if ocr_data["words"]:
        print()
        print(f"FIRST 20 BOUNDING BOXES (of {len(ocr_data['words'])}):")
        for w in ocr_data["words"][:20]:
            print(
                f"  [{w['confidence']:3d}%] "
                f"bbox({w['bbox']['x']},{w['bbox']['y']},{w['bbox']['w']},{w['bbox']['h']}) "
                f"{w['text']}"
            )

    results_path = output_dir / f"{image_path.stem}_ocr.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(ocr_data, f, ensure_ascii=False, indent=2)
    print()
    print(f"Full results saved to: {results_path}")


if __name__ == "__main__":
    main()

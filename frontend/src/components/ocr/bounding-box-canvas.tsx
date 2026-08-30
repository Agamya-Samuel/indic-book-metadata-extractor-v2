"use client";

import { useRef, useState, useEffect, useCallback, memo } from "react";
import { Stage, Layer, Image as KonvaImage, Rect, Group } from "react-konva";
import type Konva from "konva";
import type { OcrWord } from "@/lib/api";
import { Button } from "@/components/shared/button";

interface BoundingBoxCanvasProps {
  imageUrl: string;
  boxes: OcrWord[];
  selectedIndex?: number;
  onBoxClick?: (index: number) => void;
  highlightLowConfidence?: boolean;
  lowConfidenceThreshold?: number;
}

interface ImageDimensions {
  naturalWidth: number;
  naturalHeight: number;
}

export function scaleBox(
  box: { x: number; y: number; w: number; h: number },
  imageWidth: number,
  imageHeight: number,
  canvasWidth: number,
  canvasHeight: number,
): { x: number; y: number; w: number; h: number } {
  const scaleX = canvasWidth / imageWidth;
  const scaleY = canvasHeight / imageHeight;
  return {
    x: box.x * scaleX,
    y: box.y * scaleY,
    w: box.w * scaleX,
    h: box.h * scaleY,
  };
}

/**
 * Confidence color tokens — these render inside the Konva canvas, so we
 * keep them as raw RGB. They map visually to the same success/warning/danger
 * tokens used elsewhere in the system.
 */
function getConfidenceColor(confidence: number, lowThreshold: number): string {
  if (confidence >= 80) return "rgb(34, 197, 94)"; // success-500
  if (confidence >= lowThreshold) return "rgb(234, 179, 8)"; // warning-500
  return "rgb(239, 68, 68)"; // danger-500
}

interface BBoxRectProps {
  scaled: { x: number; y: number; w: number; h: number };
  isSelected: boolean;
  isLowConf: boolean;
  strokeColor: string;
  onClick: () => void;
}

const BBoxRect = memo(function BBoxRect({
  scaled,
  isSelected,
  isLowConf,
  strokeColor,
  onClick,
}: BBoxRectProps) {
  return (
    <Rect
      x={scaled.x}
      y={scaled.y}
      width={scaled.w}
      height={scaled.h}
      fill={
        isSelected
          ? "rgba(56, 132, 230, 0.20)"
          : isLowConf
            ? "rgba(239, 68, 68, 0.08)"
            : "transparent"
      }
      stroke={isSelected ? "rgb(56, 132, 230)" : strokeColor}
      strokeWidth={isSelected ? 2.5 : 1}
      onClick={onClick}
      onTap={onClick}
    />
  );
});

function BoundingBoxCanvas({
  imageUrl,
  boxes,
  selectedIndex,
  onBoxClick,
  highlightLowConfidence = true,
  lowConfidenceThreshold = 60,
}: BoundingBoxCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<Konva.Stage>(null);

  const [imgDims, setImgDims] = useState<ImageDimensions>({
    naturalWidth: 1,
    naturalHeight: 1,
  });
  const [canvasSize, setCanvasSize] = useState({ width: 800, height: 600 });
  const [zoom, setZoom] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [loadedImage, setLoadedImage] = useState<HTMLImageElement | null>(null);

  useEffect(() => {
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      setLoadedImage(img);
      setImgDims({
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
      });
    };
    img.src = imageUrl;
  }, [imageUrl]);

  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        const aspectRatio =
          imgDims.naturalWidth / imgDims.naturalHeight || 0.75;
        const height = Math.min(width / aspectRatio, 700);
        setCanvasSize({ width: Math.floor(width), height: Math.floor(height) });
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [imgDims]);

  const handleWheel = useCallback(
    (e: Konva.KonvaEventObject<WheelEvent>) => {
      e.evt.preventDefault();
      const stage = stageRef.current;
      if (!stage) return;

      const oldZoom = zoom;
      const scaleBy = 1.08;
      const newZoom = e.evt.deltaY < 0 ? oldZoom * scaleBy : oldZoom / scaleBy;
      const clampedZoom = Math.max(0.3, Math.min(5, newZoom));

      const pointer = stage.getPointerPosition();
      if (!pointer) {
        setZoom(clampedZoom);
        return;
      }

      const mousePointTo = {
        x: (pointer.x - position.x) / oldZoom,
        y: (pointer.y - position.y) / oldZoom,
      };

      setPosition({
        x: pointer.x - mousePointTo.x * clampedZoom,
        y: pointer.y - mousePointTo.y * clampedZoom,
      });
      setZoom(clampedZoom);
    },
    [zoom, position],
  );

  const handleBoxClick = useCallback(
    (index: number) => {
      if (!onBoxClick) return;
      onBoxClick(index);
    },
    [onBoxClick],
  );

  const handleResetView = useCallback(() => {
    setZoom(1);
    setPosition({ x: 0, y: 0 });
  }, []);

  const selectedWord =
    typeof selectedIndex === "number" ? boxes[selectedIndex] : undefined;

  return (
    <div ref={containerRef} className="relative w-full">
      {/* Live region for screen readers — the Konva canvas itself is one
          big role="img" so we need to announce selection changes manually. */}
      <p className="sr-only" role="status" aria-live="polite">
        {selectedWord
          ? `Selected: ${selectedWord.text}, confidence ${selectedWord.confidence} percent.`
          : ""}
      </p>

      <div className="overflow-hidden rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface-sunken)]">
        <Stage
          ref={stageRef}
          width={canvasSize.width}
          height={canvasSize.height}
          scaleX={zoom}
          scaleY={zoom}
          x={position.x}
          y={position.y}
          onWheel={handleWheel}
          draggable
          onDragEnd={(e) => {
            setPosition({ x: e.target.x(), y: e.target.y() });
          }}
          role="img"
          aria-label={`Page image with ${boxes.length} detected text regions. Zoom: ${Math.round(zoom * 100)}%`}
        >
          <Layer>
            {loadedImage && (
              <KonvaImage
                image={loadedImage}
                width={canvasSize.width}
                height={canvasSize.height}
              />
            )}
            {boxes.map((box, i) => {
              const scaled = scaleBox(
                box.bbox,
                imgDims.naturalWidth,
                imgDims.naturalHeight,
                canvasSize.width,
                canvasSize.height,
              );
              const isSelected = i === selectedIndex;
              const isLowConf =
                highlightLowConfidence && box.confidence < lowConfidenceThreshold;

              return (
                <Group key={`box-${i}-${box.word_num}-${box.line_num}`}>
                  <BBoxRect
                    scaled={scaled}
                    isSelected={isSelected}
                    isLowConf={isLowConf}
                    strokeColor={getConfidenceColor(
                      box.confidence,
                      lowConfidenceThreshold,
                    )}
                    onClick={() => handleBoxClick(i)}
                  />
                </Group>
              );
            })}
          </Layer>
        </Stage>
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[var(--text-xs)] text-[var(--text-muted)]">
        <span className="font-mono tabular-nums">
          {boxes.length} words · zoom {Math.round(zoom * 100)}%
        </span>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-1 w-3 rounded-full bg-[var(--success-500)]"
            />
            High
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-1 w-3 rounded-full bg-[var(--warning-500)]"
            />
            Medium
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-1 w-3 rounded-full bg-[var(--danger-500)]"
            />
            Low
          </span>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleResetView}
        >
          Reset view
        </Button>
      </div>
    </div>
  );
}

export default BoundingBoxCanvas;

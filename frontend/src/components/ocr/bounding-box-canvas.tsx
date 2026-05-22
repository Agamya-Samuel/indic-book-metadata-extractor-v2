"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import { Stage, Layer, Image as KonvaImage, Rect, Group } from "react-konva";
import type Konva from "konva";
import type { OcrWord } from "@/lib/api";

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
  canvasHeight: number
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

function getConfidenceColor(
  confidence: number,
  lowThreshold: number
): string {
  if (confidence >= 80) return "#22c55e";
  if (confidence >= lowThreshold) return "#eab308";
  return "#ef4444";
}

export default function BoundingBoxCanvas({
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
      setImgDims({ naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight });
    };
    img.src = imageUrl;
  }, [imageUrl]);

  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        const aspectRatio = imgDims.naturalWidth / imgDims.naturalHeight || 0.75;
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
    [zoom, position]
  );

  const handleBoxClick = useCallback(
    (index: number) => {
      if (!onBoxClick) return;
      onBoxClick(index);
    },
    [onBoxClick]
  );

  const handleResetView = useCallback(() => {
    setZoom(1);
    setPosition({ x: 0, y: 0 });
  }, []);

  return (
    <div ref={containerRef} className="relative w-full">
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
        className="bg-gray-100 border rounded"
      >
        <Layer>
          {loadedImage && (
            <KonvaImage image={loadedImage} width={canvasSize.width} height={canvasSize.height} />
          )}
          {boxes.map((box, i) => {
            const scaled = scaleBox(
              box.bbox,
              imgDims.naturalWidth,
              imgDims.naturalHeight,
              canvasSize.width,
              canvasSize.height
            );
            const isSelected = i === selectedIndex;
            const isLowConf = highlightLowConfidence && box.confidence < lowConfidenceThreshold;

            return (
              <Group key={`box-${i}-${box.word_num}-${box.line_num}`}>
                <Rect
                  x={scaled.x}
                  y={scaled.y}
                  width={scaled.w}
                  height={scaled.h}
                  fill={isSelected ? "rgba(59,130,246,0.25)" : isLowConf ? "rgba(239,68,68,0.1)" : "transparent"}
                  stroke={
                    isSelected
                      ? "#3b82f6"
                      : getConfidenceColor(box.confidence, lowConfidenceThreshold)
                  }
                  strokeWidth={isSelected ? 2.5 : 1}
                  onClick={() => handleBoxClick(i)}
                  onTap={() => handleBoxClick(i)}
                />
              </Group>
            );
          })}
        </Layer>
      </Stage>

      <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
        <span>
          {boxes.length} words &bull; Zoom: {Math.round(zoom * 100)}%
        </span>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-1 rounded bg-green-500" /> High
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-1 rounded bg-yellow-500" /> Medium
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-1 rounded bg-red-500" /> Low
          </span>
        </div>
        <button
          onClick={handleResetView}
          className="px-2 py-1 text-xs border rounded hover:bg-gray-100"
        >
          Reset View
        </button>
      </div>
    </div>
  );
}

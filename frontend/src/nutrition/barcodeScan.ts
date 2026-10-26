// Barcode decoding in the browser, with no external service.
// Uses the native BarcodeDetector where the browser has one, otherwise ZXing (loaded on demand).

const RETAIL_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e"];

interface DetectedBarcode { rawValue: string }
interface BarcodeDetectorLike { detect(source: ImageBitmapSource): Promise<DetectedBarcode[]> }
type BarcodeDetectorCtor = new (opts: { formats: string[] }) => BarcodeDetectorLike;

function nativeDetector(): BarcodeDetectorLike | null {
  const Ctor = (globalThis as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector;
  return Ctor ? new Ctor({ formats: RETAIL_FORMATS }) : null;
}

async function zxingReader() {
  const [{ BrowserMultiFormatReader }, { BarcodeFormat, DecodeHintType }] = await Promise.all([
    import("@zxing/browser"), import("@zxing/library"),
  ]);
  const hints = new Map();
  hints.set(DecodeHintType.POSSIBLE_FORMATS, [BarcodeFormat.EAN_13, BarcodeFormat.EAN_8, BarcodeFormat.UPC_A, BarcodeFormat.UPC_E]);
  hints.set(DecodeHintType.TRY_HARDER, true);
  return new BrowserMultiFormatReader(hints);
}

/** Decode a barcode from a photo. Returns the digits, or null if no barcode was found. */
export async function decodeImageFile(file: Blob): Promise<string | null> {
  const native = nativeDetector();
  if (native) {
    try {
      const found = await native.detect(await createImageBitmap(file));
      if (found[0]?.rawValue) return found[0].rawValue;
    } catch { /* fall through to ZXing */ }
  }
  const reader = await zxingReader();
  const url = URL.createObjectURL(file);
  try {
    return (await reader.decodeFromImageUrl(url)).getText();
  } catch {
    return null;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export interface CameraScan { stop: () => void }

/** Start scanning from the camera into `video`. Calls onCode once, then stops. */
export async function startCameraScan(video: HTMLVideoElement, onCode: (code: string) => void): Promise<CameraScan> {
  const reader = await zxingReader();
  let done = false;
  const controls = await reader.decodeFromVideoDevice(undefined, video, (result, _err, ctl) => {
    if (result && !done) {
      done = true;
      ctl.stop();
      onCode(result.getText());
    }
  });
  return { stop: () => controls.stop() };
}

export function cameraAvailable(): boolean {
  return typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
}

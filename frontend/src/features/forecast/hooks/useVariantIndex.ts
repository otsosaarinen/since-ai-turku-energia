import { useEffect, useState } from "react";
import { dataUrl } from "@/lib/config";
import type { VariantIndex } from "../types";

/** The validation error of every precomputed model variant, or null while loading or when the file does not exist. */
export function useVariantIndex(): VariantIndex | null {
  const [variantIndex, setVariantIndex] = useState<VariantIndex | null>(null);
  useEffect(() => {
    fetch(dataUrl("variants/index"))
      .then((response) => (response.ok ? response.json() : null))
      .then(setVariantIndex)
      .catch(() => setVariantIndex(null));
  }, []);
  return variantIndex;
}

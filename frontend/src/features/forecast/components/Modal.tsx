"use client";

import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Icon } from "@/components/Icon";
import { Button, Card } from "@/design-system/the-reading-room-3066fa";
import { headingClass } from "@/lib/styles";

interface ModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

/** A pop-up on top of the page (drawn on the page body so nothing can cover it). Closes with the X, a click outside, or Escape. */
export function Modal({ title, onClose, children }: ModalProps) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-foreground/60 p-4" onClick={onClose}>
      <Card role="dialog" aria-modal="true" aria-label={title} className="max-h-full w-full max-w-lg space-y-3 overflow-y-auto p-5" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <h2 className={`${headingClass} text-2xl`}>{title}.</h2>
          <Button type="button" size="sm" variant="outline" aria-label="Close" onClick={onClose}><Icon name="x" /></Button>
        </div>
        {children}
      </Card>
    </div>,
    document.body,
  );
}

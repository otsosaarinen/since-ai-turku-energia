"use client";

import { useState } from "react";
import { Button } from "@/design-system/the-reading-room-3066fa";
import { Modal } from "./Modal";

/** "How to use" button that opens the plain-language explanation in a pop-up. */
export function AboutDemo() {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <>
      <Button type="button" size="sm" variant="outline" aria-haspopup="dialog" onClick={() => setIsOpen(true)}>How to use</Button>
      {isOpen && (
        <Modal title="How to use" onClose={() => setIsOpen(false)}>
          <p>
            We trained a model to predict the Finnish imbalance price (what the grid operator charges for balancing the grid) 10 hours ahead, every hour.
          </p>
          <p>
            The chart replays a past month as if it were live. Press <b>Play</b> to move through time, or drag the slider to any moment.
          </p>
          <ul className="list-disc space-y-1 pl-5">
            <li>The orange line is the most likely price.</li>
            <li>The blue band is the likely range.</li>
            <li>The red line is the real price.</li>
            <li>The two boxes show the risk of an exceptionally high or low price.</li>
            <li>Period: Validation is a month where the real prices are known, so you can see how good the forecast was. Test forecast is the following month, without real prices.</li>
            <li>Forecast inputs: switch the solar, wind or consumption forecast off to see a model trained without it. The average error shows how much worse it gets, so you can see how much the model relies on each one.</li>
          </ul>
        </Modal>
      )}
    </>
  );
}

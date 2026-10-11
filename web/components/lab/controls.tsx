"use client";

import { Dices } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import { NOISE_LABEL, randomSeed, type LabNoise, type NoiseChannel } from "./lab-api";

/** Parse an integer text field against [min, max]; returns the value or an error message. */
export function parseIntField(text: string, min: number, max: number, name: string): { value?: number; error?: string } {
  if (!/^\d+$/.test(text.trim())) return { error: `${name} must be a whole number.` };
  const v = Number(text);
  if (v < min || v > max) return { error: `${name} must be between ${min.toLocaleString("en-US")} and ${max.toLocaleString("en-US")}.` };
  return { value: v };
}

/** Labelled control group with a mono caption; the left config rail is built from these. */
export function ControlGroup({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <fieldset className={cn("grid gap-4 border-t border-border pt-4 first:border-0 first:pt-0", className)}>
      <legend className="label-mono float-left mb-0 w-full text-subtle">{title}</legend>
      {children}
    </fieldset>
  );
}

export function SliderField({
  id,
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  hint,
  disabled,
  format = (v: number) => String(v),
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  hint?: React.ReactNode;
  disabled?: boolean;
  format?: (v: number) => string;
}) {
  return (
    <Field
      id={id}
      hint={hint}
      label={
        <span className="flex justify-between">
          <span>{label}</span>
          <span className={cn("tnum font-mono", disabled ? "text-subtle" : "text-foreground")}>{format(value)}</span>
        </span>
      }
    >
      <ThumbLabel label={label} valueText={format(value)}>
      <Slider
        id={id}
        aria-label={label}
        aria-valuetext={format(value)}
        min={min}
        max={max}
        step={step}
        value={[value]}
        disabled={disabled}
        onValueChange={(v) => onChange(v[0] ?? min)}
      />
      </ThumbLabel>
    </Field>
  );
}

/**
 * The frozen ui/slider forwards aria-label to the Radix Root, not to the focusable thumb
 * (role="slider"), so screen readers announce an unnamed slider. Until the primitive forwards it
 * (proposed in handoffs/K-web-D.md), name the thumb here.
 */
function ThumbLabel({ label, valueText, children }: { label: string; valueText: string; children: React.ReactNode }) {
  const ref = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    ref.current?.querySelectorAll('[role="slider"]').forEach((el) => {
      el.setAttribute("aria-label", label);
      el.setAttribute("aria-valuetext", valueText);
    });
  });
  return <div ref={ref}>{children}</div>;
}

export function IntField({
  id,
  label,
  text,
  onText,
  error,
  hint,
  action,
}: {
  id: string;
  label: string;
  text: string;
  onText: (t: string) => void;
  error?: string;
  hint?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <Field id={id} label={label} error={error} hint={hint}>
      <div className="flex gap-1.5">
        <Input
          id={id}
          type="text"
          inputMode="numeric"
          className="tnum font-mono"
          value={text}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
          onChange={(e) => onText(e.target.value)}
        />
        {action}
      </div>
    </Field>
  );
}

export function SeedField({ id, text, onText, error }: { id: string; text: string; onText: (t: string) => void; error?: string }) {
  return (
    <IntField
      id={id}
      label="Seed"
      text={text}
      onText={onText}
      error={error}
      hint="Same seed → same note, same samples."
      action={
        <Button variant="secondary" size="icon" aria-label="Random seed" title="Random seed" onClick={() => onText(String(randomSeed()))}>
          <Dices aria-hidden />
        </Button>
      }
    />
  );
}

export function NoiseControls({ idPrefix, noise, onChange, hint }: { idPrefix: string; noise: LabNoise; onChange: (n: LabNoise) => void; hint?: string }) {
  const strengthName = noise.channel === "amplitude_damping" ? "γ" : "p";
  return (
    <>
      <Field id={`${idPrefix}-channel`} label="Noise channel" hint={hint}>
        <Select
          value={noise.channel}
          onValueChange={(v) => {
            const channel = v as NoiseChannel;
            onChange({ channel, strength: channel === "none" ? 0 : noise.strength || 0.05 });
          }}
        >
          <SelectTrigger id={`${idPrefix}-channel`} aria-label="Noise channel">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(NOISE_LABEL) as NoiseChannel[]).map((c) => (
              <SelectItem key={c} value={c}>
                {NOISE_LABEL[c]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <SliderField
        id={`${idPrefix}-strength`}
        label={`Strength ${strengthName}`}
        value={noise.strength ?? 0}
        min={0}
        max={0.5}
        step={0.01}
        disabled={noise.channel === "none"}
        hint={noise.channel === "none" ? "Pick a channel to set its strength." : "Hypothetical value, not a device calibration."}
        format={(v) => v.toFixed(2)}
        onChange={(strength) => onChange({ ...noise, strength })}
      />
    </>
  );
}

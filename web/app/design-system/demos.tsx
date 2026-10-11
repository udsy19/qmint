"use client";

import { FlaskConical, Play, ShieldQuestion, Swords } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandFooter,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Dialog, DialogBody, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/toast";

export function FormDemo() {
  const [n, setN] = React.useState(4);
  const [seed, setSeed] = React.useState("2026");
  const seedInvalid = !/^\d+$/.test(seed);
  return (
    <div className="grid max-w-sm gap-5">
      <Field id="ds-protocol" label="Protocol">
        <Select defaultValue="wiesner_ideal">
          <SelectTrigger id="ds-protocol" aria-label="Protocol">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="wiesner_ideal">wiesner_ideal · W1</SelectItem>
            <SelectItem value="wiesner_noisy">wiesner_noisy · W2</SelectItem>
            <SelectItem value="s_money_kent_2022_ideal_2site" disabled>
              s_money_kent_2022_ideal_2site · S1
            </SelectItem>
          </SelectContent>
        </Select>
      </Field>
      <Field id="ds-n" label={<span className="flex justify-between"><span>Qubits n</span><span className="tnum font-mono text-foreground">{n}</span></span>} hint="Statevector cap: n ≤ 8">
        <Slider id="ds-n" aria-label="Qubits" min={1} max={8} step={1} value={[n]} onValueChange={(v) => setN(v[0] ?? 1)} />
      </Field>
      <Field id="ds-seed" label="Seed" error={seedInvalid ? "Seed must be a non-negative integer." : undefined} hint="Same seed → same token and counts.">
        <Input id="ds-seed" type="number" inputMode="numeric" value={seed} aria-invalid={seedInvalid || undefined} aria-describedby={seedInvalid ? "ds-seed-error" : "ds-seed-hint"} onChange={(e) => setSeed(e.target.value)} />
      </Field>
    </div>
  );
}

export function TabsDemo() {
  return (
    <Tabs defaultValue="preparation" className="max-w-xl">
      <TabsList aria-label="Run detail">
        <TabsTrigger value="preparation">Preparation</TabsTrigger>
        <TabsTrigger value="circuit">Circuit</TabsTrigger>
        <TabsTrigger value="statistics">Statistics</TabsTrigger>
        <TabsTrigger value="provenance">Provenance</TabsTrigger>
      </TabsList>
      <TabsContent value="preparation" className="text-sm text-muted">Per-qubit basis and bit (issuer view, demo only).</TabsContent>
      <TabsContent value="circuit" className="text-sm text-muted">Prepare → channel → verify; resource counts.</TabsContent>
      <TabsContent value="statistics" className="text-sm text-muted">Outcome distribution and acceptance with interval.</TabsContent>
      <TabsContent value="provenance" className="text-sm text-muted">Seed, shots, software versions, circuit SHA-256.</TabsContent>
    </Tabs>
  );
}

export function OverlayDemos() {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Command palette <Kbd>⌘</Kbd>
        <Kbd>K</Kbd>
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Jump to a tool or run…" />
        <CommandList>
          <CommandEmpty>No matching tool. Try “mint” or “attack”.</CommandEmpty>
          <CommandGroup heading="Laboratory">
            <CommandItem onSelect={() => setOpen(false)}>
              <FlaskConical aria-hidden /> Mint a token
            </CommandItem>
            <CommandItem onSelect={() => setOpen(false)}>
              <Swords aria-hidden /> Run a counterfeiting attack
            </CommandItem>
            <CommandItem onSelect={() => setOpen(false)}>
              <ShieldQuestion aria-hidden /> Request a certificate
            </CommandItem>
          </CommandGroup>
        </CommandList>
        <CommandFooter>3 results</CommandFooter>
      </CommandDialog>
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="secondary">Open dialog</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Export certificate data</DialogTitle>
            <DialogDescription>UNCERTIFIED results export with their reasons. Nothing here is a formal proof.</DialogDescription>
          </DialogHeader>
          <DialogBody className="font-mono text-xs text-muted">certificate.json · 2.1 kB</DialogBody>
          <DialogFooter>
            <Button variant="ghost">Cancel</Button>
            <Button variant="primary">Download JSON</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Button variant="secondary" onClick={() => toast.success("Run complete", { description: "wiesner_ideal · n=4 · seed 2026 · 4 000 shots" })}>
        Toast: success
      </Button>
      <Button variant="secondary" onClick={() => toast.error("API timed out", { description: "POST /api/v1/lab/mint exceeded 15 s. Retry with fewer shots." })}>
        Toast: error
      </Button>
      <Button variant="accent">
        <Play aria-hidden /> Run experiment
      </Button>
    </div>
  );
}

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import MarkdownLatex from "@/lib/markdown";
import {
  DialogExample,
  DropdownExample,
  TooltipExample,
  HintPanel,
} from "@/components/DesignInteractiveExamples";
import { BookOpen, FileText, RefreshCw, Sparkles, AlertTriangle } from "lucide-react";

/* ─── Layout helpers ─────────────────────────────────────── */

function Section({ title, id, children }: { title: string; id: string; children: React.ReactNode }) {
  return (
    <section id={id} className="space-y-6 py-10 border-t border-border first:border-t-0 first:pt-0">
      <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Row({ label, children }: { label?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      {label && <p className="text-xs text-muted-foreground">{label}</p>}
      <div className="flex flex-wrap items-start gap-3">{children}</div>
    </div>
  );
}

function Swatch({ label, className, hex }: { label: string; className: string; hex: string }) {
  return (
    <div className="space-y-1.5">
      <div className={`h-10 w-24 rounded-md border border-border ${className}`} />
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-mono text-xs text-muted-foreground/70">{hex}</p>
    </div>
  );
}

/* ─── Product sample data ────────────────────────────────── */

const PROBLEM_MD = `Let $f : \\mathbb{R} \\to \\mathbb{R}$ be differentiable with $f(0) = 1$
and $f'(x) = f(x)$ for all $x \\in \\mathbb{R}$. Show that $f(x) = e^x$.`;

const PROBLEM_CONTEXT_MD = `**Context.** This characterisation of the exponential function appears across
mathematics: in ODE theory as the unique solution to $y' = y$, in complex
analysis via Euler's formula $e^{i\\theta} = \\cos\\theta + i\\sin\\theta$, and in
quantum mechanics where it drives the time-evolution operator $U(t) = e^{-iHt/\\hbar}$.
The function you are proving unique is the eigenfunction of differentiation.`;

const NOTEBOOK_ENTRY_MD = `**Your solution** (parsed from photograph)

Let $g(x) = f(x) \\cdot e^{-x}$. By the product rule:

$$g'(x) = f'(x) e^{-x} - f(x) e^{-x} = (f'(x) - f(x)) e^{-x} = 0$$

since $f'(x) = f(x)$ by hypothesis. So $g$ is constant. Evaluating at $x = 0$:

$$g(0) = f(0) \\cdot e^0 = 1 \\cdot 1 = 1$$

Therefore $g(x) = 1$ for all $x$, which gives $f(x) = e^x$. $\\blacksquare$`;

const FEEDBACK_MD = `Good — the product rule move is exactly right, and the evaluation at $x = 0$ is
clean. One thing to make explicit: you need $e^{-x} \\neq 0$ to conclude
$f'(x) = f(x)$ from $g'(x) = 0$. Worth one sentence. The argument as written
works for continuity; uniqueness follows from the same $g$ construction applied
to *any* two solutions.`;

/* ─── Page ───────────────────────────────────────────────── */

export default function DesignPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Sticky TOC for navigation on the design page */}
      <div className="border-b border-border bg-muted/40">
        <div className="mx-auto max-w-3xl px-5 py-2">
          <nav className="flex flex-wrap gap-x-5 gap-y-1">
            {[
              ["fonts", "Fonts"],
              ["colours", "Colours"],
              ["type", "Typography"],
              ["motion", "Motion"],
              ["buttons", "Buttons"],
              ["cards", "Cards"],
              ["forms", "Forms"],
              ["badges", "Badges"],
              ["alerts", "Alerts"],
              ["tabs", "Tabs"],
              ["overlays", "Overlays"],
              ["loading", "Loading"],
              ["product", "Product"],
            ].map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors duration-[var(--duration-fast)]"
              >
                {label}
              </a>
            ))}
          </nav>
        </div>
      </div>

      <div className="mx-auto max-w-3xl px-5 pb-24">
        {/* Header */}
        <div className="py-10">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Design reference
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Living style guide — design tokens, shadcn components, and product samples.
            Use this page to verify visual regressions and explore the system.
          </p>
        </div>

        {/* ── FONTS ── */}
        <Section title="Fonts — comparison" id="fonts">
          <p className="text-sm text-muted-foreground -mt-2">
            Same content rendered in each serif candidate. Remaining sections default to
            Source Serif 4.
          </p>

          <div className="grid gap-6 sm:grid-cols-2">
            {/* Lora — chosen default */}
            <div className="space-y-3 rounded-lg border-2 border-amber p-5">
              <div className="flex items-center gap-2">
                <p className="text-xs font-semibold uppercase tracking-widest text-amber">
                  Lora
                </p>
                <Badge variant="default" className="h-4 text-[10px]">Chosen</Badge>
              </div>
              <p className="font-serif text-base leading-relaxed text-foreground">
                Let <em>f</em> : ℝ → ℝ be differentiable with <em>f</em>(0) = 1
                and <em>f</em>′(<em>x</em>) = <em>f</em>(<em>x</em>) for all <em>x</em>.
                Show that <em>f</em>(<em>x</em>) = e<sup><em>x</em></sup>.
              </p>
              <p className="font-serif text-sm leading-[1.7] text-muted-foreground">
                This characterisation of the exponential function appears across
                mathematics: in ODE theory as the unique solution to <em>y</em>′ = <em>y</em>,
                in complex analysis via Euler's formula, and in quantum mechanics in the
                time-evolution operator. The function you prove unique is the eigenfunction
                of differentiation.
              </p>
              <p className="font-serif text-sm leading-[1.7] text-foreground">
                Good — the product rule move is exactly right, and the evaluation at
                <em> x </em> = 0 is clean. One thing to make explicit: you need
                <em> e</em><sup>−<em>x</em></sup> ≠ 0 to conclude the function is constant.
              </p>
              <div className="pt-1 space-y-0.5">
                <p className="font-serif text-2xl font-semibold">Heading Aa</p>
                <p className="font-serif text-lg font-medium">Subheading Aa</p>
                <p className="font-serif text-base">Body text 0123456789</p>
                <p className="font-serif text-sm text-muted-foreground">Caption text — abcdefghijklm</p>
              </div>
            </div>

            {/* Source Serif 4 — alternative */}
            <div className="space-y-3 rounded-lg border border-border p-5 opacity-75">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Source Serif 4 — alternative
              </p>
              <p className="font-source-serif text-base leading-relaxed text-foreground">
                Let <em>f</em> : ℝ → ℝ be differentiable with <em>f</em>(0) = 1
                and <em>f</em>′(<em>x</em>) = <em>f</em>(<em>x</em>) for all <em>x</em>.
                Show that <em>f</em>(<em>x</em>) = e<sup><em>x</em></sup>.
              </p>
              <p className="font-source-serif text-sm leading-[1.7] text-muted-foreground">
                This characterisation of the exponential function appears across
                mathematics: in ODE theory as the unique solution to <em>y</em>′ = <em>y</em>,
                in complex analysis via Euler's formula, and in quantum mechanics in the
                time-evolution operator. The function you prove unique is the eigenfunction
                of differentiation.
              </p>
              <p className="font-source-serif text-sm leading-[1.7] text-foreground">
                Good — the product rule move is exactly right, and the evaluation at
                <em> x </em> = 0 is clean. One thing to make explicit: you need
                <em> e</em><sup>−<em>x</em></sup> ≠ 0 to conclude the function is constant.
              </p>
              <div className="pt-1 space-y-0.5">
                <p className="font-source-serif text-2xl font-semibold">Heading Aa</p>
                <p className="font-source-serif text-lg font-medium">Subheading Aa</p>
                <p className="font-source-serif text-base">Body text 0123456789</p>
                <p className="font-source-serif text-sm text-muted-foreground">Caption text — abcdefghijklm</p>
              </div>
            </div>
          </div>

          {/* Monospace */}
          <div className="rounded-lg border border-border p-5 space-y-2">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              JetBrains Mono — equations &amp; code
            </p>
            <p className="font-mono text-sm leading-relaxed text-foreground">
              f(x) = e^x &nbsp;&nbsp; g(x) = f(x)·e^(−x) &nbsp;&nbsp; g′(x) = 0
            </p>
            <p className="font-mono text-sm text-muted-foreground">
              const result = await supabase.from(&apos;nodes&apos;).select(&apos;*&apos;)
            </p>
          </div>
        </Section>

        {/* ── COLOURS ── */}
        <Section title="Colours" id="colours">
          <Row label="Primary accent — honey amber">
            <Swatch label="amber" hex="#B8860B" className="bg-amber" />
            <Swatch label="amber-subtle" hex="oklch(0.958 0.025 82)" className="bg-amber-subtle" />
            <Swatch label="primary" hex="= amber" className="bg-primary" />
            <Swatch label="ring" hex="= amber" className="bg-ring" />
          </Row>
          <Row label="Secondary accent — muted forest">
            <Swatch label="forest" hex="#4A7066" className="bg-forest" />
            <Swatch label="forest-subtle" hex="oklch(0.945 0.020 170)" className="bg-forest-subtle" />
            <Swatch label="secondary" hex="= forest" className="bg-secondary" />
          </Row>
          <Row label="Neutrals">
            <Swatch label="background" hex="#FAF7F0" className="bg-background border-2" />
            <Swatch label="card" hex="oklch(0.960)" className="bg-card" />
            <Swatch label="muted" hex="oklch(0.930)" className="bg-muted" />
            <Swatch label="accent" hex="oklch(0.950)" className="bg-accent" />
            <Swatch label="border" hex="oklch(0.870)" className="bg-border" />
          </Row>
          <Row label="Text">
            <Swatch label="foreground" hex="#1C1917" className="bg-foreground" />
            <Swatch label="muted-fg" hex="oklch(0.478)" className="bg-muted-foreground" />
            <Swatch label="destructive" hex="oklch(0.577)" className="bg-destructive" />
          </Row>
        </Section>

        {/* ── TYPOGRAPHY ── */}
        <Section title="Typography" id="type">
          <div className="space-y-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">h1 — 2xl semibold, sans</p>
              <p className="text-2xl font-semibold tracking-tight text-foreground">
                Ordinary Differential Equations
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">h2 — xl medium, sans</p>
              <p className="text-xl font-medium text-foreground">
                Second-Order Linear Equations
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">h3 — base semibold, sans</p>
              <p className="text-base font-semibold text-foreground">
                Variation of Parameters
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">body — base, serif, lh 1.7</p>
              <p className="font-serif text-base leading-[1.7] text-foreground max-w-prose">
                Working scientists are competent adults. The product gives them one thing
                at a time — a paper to work through, or a problem to solve with pen and
                paper — and trusts them to engage with it on their own terms.
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">small / caption — sm, muted</p>
              <p className="text-sm text-muted-foreground">
                Estimated 20–35 minutes · Ordinary differential equations · Difficulty: core
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">mono — sm, jetbrains</p>
              <p className="font-mono text-sm text-foreground">
                ∂²u/∂t² = c² ∇²u &nbsp;&nbsp; Δf = 0 &nbsp;&nbsp; L[y] = g(x)
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">label / nav — xs, uppercase, tracked</p>
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Skill tree · Foundations · Mathematics
              </p>
            </div>
          </div>
        </Section>

        {/* ── MOTION ── */}
        <Section title="Motion tokens" id="motion">
          <div className="rounded-lg border border-border overflow-hidden text-sm">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Token</th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Value</th>
                  <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Use for</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {[
                  ["--duration-fast", "100ms", "Hover states, colour transitions, tiny toggles"],
                  ["--duration-standard", "200ms", "Panel opens, tab switches, accordion expand"],
                  ["--duration-slow", "350ms", "Page transitions, large layout shifts"],
                  ["--ease-productive", "cubic-bezier(0, 0, 0.2, 1)", "UI responses — snappy ease-out"],
                  ["--ease-expressive", "cubic-bezier(0.4, 0, 0.2, 1)", "Content entries — balanced ease-in-out"],
                ].map(([token, value, use]) => (
                  <tr key={token}>
                    <td className="px-4 py-2.5 font-mono text-xs text-foreground">{token}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{value}</td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground">{use}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted-foreground">
            Usage: <code className="font-mono bg-muted px-1 py-0.5 rounded text-xs">transition-colors duration-[var(--duration-fast)] [transition-timing-function:var(--ease-productive)]</code>
          </p>
        </Section>

        {/* ── BUTTONS ── */}
        <Section title="Buttons" id="buttons">
          <Row label="Variants">
            <Button variant="default">Primary (amber)</Button>
            <Button variant="secondary">Secondary (forest)</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="link">Link</Button>
            <Button variant="destructive">Destructive</Button>
          </Row>
          <Row label="Sizes">
            <Button size="lg">Large</Button>
            <Button size="default">Default</Button>
            <Button size="sm">Small</Button>
            <Button size="xs">X-small</Button>
          </Row>
          <Row label="Icon">
            <Button size="icon" variant="outline"><RefreshCw className="size-4" /></Button>
            <Button size="icon-sm" variant="ghost"><BookOpen className="size-3.5" /></Button>
          </Row>
          <Row label="Disabled">
            <Button disabled>Disabled primary</Button>
            <Button variant="outline" disabled>Disabled outline</Button>
          </Row>
        </Section>

        {/* ── CARDS ── */}
        <Section title="Cards" id="cards">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Queue item</CardTitle>
                <CardDescription>Problem · Ordinary Differential Equations</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground leading-relaxed">
                A foundational problem on second-order linear ODEs. Connects to your
                interest in signal processing via the characteristic equation.
              </CardContent>
              <CardFooter className="gap-2">
                <Button size="sm">Start</Button>
                <Button size="sm" variant="ghost">Reroll</Button>
              </CardFooter>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Paper engagement</CardTitle>
                <CardDescription>Abbott et al. 2016 · LIGO</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground leading-relaxed">
                The first detection of gravitational waves from a binary black hole merger.
                Connects directly to your interest in gravitational wave physics.
              </CardContent>
              <CardFooter className="gap-2">
                <Button size="sm" variant="secondary">Read paper</Button>
                <Button size="sm" variant="ghost">Later</Button>
              </CardFooter>
            </Card>
          </div>
        </Section>

        {/* ── FORMS ── */}
        <Section title="Form inputs" id="forms">
          <div className="max-w-sm space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">Free-text intent</label>
              <Input placeholder="What do you wish you understood better?" />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">Add an interest</label>
              <Input placeholder="e.g. Kalman filters, Meissner effect…" />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">Paper answer</label>
              <Textarea
                placeholder="Your response (2–4 sentences)…"
                className="font-serif text-sm leading-relaxed"
                rows={4}
              />
            </div>
          </div>
        </Section>

        {/* ── BADGES ── */}
        <Section title="Badges" id="badges">
          <Row label="Mode badges">
            <Badge variant="default">Problem</Badge>
            <Badge variant="secondary">Paper</Badge>
            <Badge variant="outline">Refresher</Badge>
            <Badge variant="ghost">Suggested</Badge>
          </Row>
          <Row label="Node state badges">
            <Badge variant="outline" className="border-amber text-amber">Active</Badge>
            <Badge variant="outline" className="border-forest text-forest">Comfortable</Badge>
            <Badge variant="ghost">Unseen</Badge>
            <Badge variant="destructive">Struggling</Badge>
          </Row>
        </Section>

        {/* ── ALERTS ── */}
        <Section title="Alerts" id="alerts">
          <Alert>
            <Sparkles className="size-4" />
            <AlertTitle>Cross-pollination suggestion</AlertTitle>
            <AlertDescription>
              Three users in adjacent areas have explored <strong>Topological Insulators</strong>.
              It neighbours your solid-state interests.
            </AlertDescription>
          </Alert>

          <Alert variant="destructive">
            <AlertTriangle className="size-4" />
            <AlertTitle>Grade disputed</AlertTitle>
            <AlertDescription>
              Your dispute has been queued for operator review. No automated re-grading in v1.
            </AlertDescription>
          </Alert>

          <Alert>
            <FileText className="size-4" />
            <AlertTitle>Parse needs review</AlertTitle>
            <AlertDescription>
              The image was parsed but some symbols may need correction. Review the
              markdown below before submitting.
            </AlertDescription>
          </Alert>
        </Section>

        {/* ── TABS ── */}
        <Section title="Tabs" id="tabs">
          <Tabs defaultValue="problem">
            <TabsList>
              <TabsTrigger value="problem">Problem</TabsTrigger>
              <TabsTrigger value="hints">Hints</TabsTrigger>
              <TabsTrigger value="notebook">Notebook</TabsTrigger>
            </TabsList>
            <TabsContent value="problem" className="pt-4">
              <p className="font-serif text-sm leading-relaxed text-muted-foreground">
                The problem statement and context would appear here.
              </p>
            </TabsContent>
            <TabsContent value="hints" className="pt-4">
              <p className="font-serif text-sm leading-relaxed text-muted-foreground">
                Progressive hints — none pre-revealed.
              </p>
            </TabsContent>
            <TabsContent value="notebook" className="pt-4">
              <p className="font-serif text-sm leading-relaxed text-muted-foreground">
                Your previous attempts on this topic.
              </p>
            </TabsContent>
          </Tabs>
        </Section>

        {/* ── OVERLAYS ── */}
        <Section title="Overlays — dialog / dropdown / tooltip" id="overlays">
          <Row>
            <DialogExample />
            <DropdownExample />
            <TooltipExample />
          </Row>
        </Section>

        {/* ── LOADING ── */}
        <Section title="Loading / skeleton" id="loading">
          <div className="space-y-4">
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">Queue item skeleton</p>
              <Card>
                <CardHeader>
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-3 w-56" />
                </CardHeader>
                <CardContent className="space-y-2">
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-4/5" />
                  <Skeleton className="h-3 w-3/5" />
                </CardContent>
              </Card>
            </div>

            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">Inline text skeleton</p>
              <div className="space-y-1.5">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
              </div>
            </div>
          </div>
        </Section>

        {/* ── PRODUCT SAMPLES ── */}
        <Section title="Product — problem statement" id="product">
          <Card>
            <CardHeader className="border-b pb-4">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <CardTitle>Characterisation of the exponential</CardTitle>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="default">Problem</Badge>
                    <Badge variant="outline">Ordinary differential equations</Badge>
                    <span className="text-xs text-muted-foreground">15–25 min</span>
                  </div>
                </div>
                <DropdownExample />
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              {/* Problem statement */}
              <div className="prose-sm max-w-none font-serif leading-[1.7] [&_.katex]:font-mono">
                <MarkdownLatex source={PROBLEM_MD} />
              </div>

              {/* Context */}
              <div className="border-l-2 border-amber pl-4">
                <p className="text-xs font-semibold uppercase tracking-widest text-amber mb-2">
                  Context
                </p>
                <div className="font-serif text-sm leading-[1.7] text-muted-foreground [&_.katex]:font-mono">
                  <MarkdownLatex source={PROBLEM_CONTEXT_MD} />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Paper "why this" block */}
          <div className="space-y-2 mt-2">
            <p className="text-xs text-muted-foreground">Paper — "why this" context block</p>
            <Card>
              <CardContent className="pt-4 space-y-4">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-forest-subtle">
                    <FileText className="size-3.5 text-forest" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-foreground">
                      Abbott et al. (2016) — Observation of Gravitational Waves from a Binary Black Hole Merger
                    </p>
                    <p className="text-xs text-muted-foreground">LIGO Scientific Collaboration · Physical Review Letters</p>
                  </div>
                </div>

                <div className="border-l-2 border-forest pl-4">
                  <p className="text-xs font-semibold uppercase tracking-widest text-forest mb-2">
                    Why this paper
                  </p>
                  <p className="font-serif text-sm leading-[1.7] text-foreground">
                    You marked gravitational wave physics as a primary interest at sign-up.
                    This is the paper that started the field of observational gravitational
                    wave astronomy — the first direct detection of a signal predicted by
                    general relativity a century earlier. It will give you an anchor for
                    everything that follows, from the LIGO detector design to the parameter
                    estimation pipeline. The matched-filtering technique described here
                    connects directly to your signal-processing interests via the concept
                    of cross-correlation in the frequency domain.
                  </p>
                </div>

                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">
                    Orienting concepts
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {[
                      ["Gravitational wave strain", "The fractional change in length, h = ΔL/L, produced by a passing wave."],
                      ["Chirp signal", "A sweep in frequency and amplitude as a binary system inspirals toward merger."],
                      ["Matched filtering", "Convolving the detector output with a template waveform to detect a known signal in noise."],
                      ["Binary black hole inspiral", "The orbital decay of two black holes as they lose energy to gravitational radiation."],
                    ].map(([term, gloss]) => (
                      <div key={term} className="rounded-md bg-muted/60 p-3 space-y-0.5">
                        <p className="text-xs font-semibold text-foreground">{term}</p>
                        <p className="text-xs text-muted-foreground leading-relaxed">{gloss}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button size="sm" variant="secondary">
                    <BookOpen className="size-3.5" /> Open paper
                  </Button>
                  <Button size="sm" variant="outline">Bookmark</Button>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Hint disclosure panel */}
          <div className="space-y-2 mt-2">
            <p className="text-xs text-muted-foreground">Hint disclosure panel (interactive)</p>
            <Card>
              <CardHeader>
                <CardTitle>Hints</CardTitle>
                <CardDescription>Pre-generated. Progressive. Never solve.</CardDescription>
              </CardHeader>
              <CardContent>
                <HintPanel />
              </CardContent>
            </Card>
          </div>

          {/* Notebook entry */}
          <div className="space-y-2 mt-2">
            <p className="text-xs text-muted-foreground">Notebook entry</p>
            <Card>
              <CardHeader className="border-b pb-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle>Characterisation of the exponential</CardTitle>
                    <CardDescription>12 May 2026 · Ordinary differential equations</CardDescription>
                  </div>
                  <Badge variant="outline" className="border-forest text-forest shrink-0">Correct</Badge>
                </div>
              </CardHeader>
              <CardContent className="pt-4 space-y-5">
                <div className="font-serif text-sm leading-[1.7] text-foreground [&_.katex]:font-mono">
                  <MarkdownLatex source={NOTEBOOK_ENTRY_MD} />
                </div>

                <div className="border-l-2 border-amber pl-4">
                  <p className="text-xs font-semibold uppercase tracking-widest text-amber mb-2">
                    Feedback
                  </p>
                  <div className="font-serif text-sm leading-[1.7] text-muted-foreground [&_.katex]:font-mono">
                    <MarkdownLatex source={FEEDBACK_MD} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Node detail side-panel mockup */}
          <div className="space-y-2 mt-2">
            <p className="text-xs text-muted-foreground">Node detail panel (skill tree)</p>
            <div className="rounded-lg border border-border overflow-hidden">
              {/* Simulated panel layout */}
              <div className="grid sm:grid-cols-[1fr_300px]">
                {/* Left — stub graph area */}
                <div className="bg-muted/30 flex items-center justify-center p-8 min-h-48">
                  <p className="text-xs text-muted-foreground">← Skill tree canvas</p>
                </div>
                {/* Right — node panel */}
                <div className="border-l border-border bg-card p-5 space-y-4">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                        Foundation · Mathematics
                      </p>
                      <Badge variant="outline" className="border-amber text-amber text-xs">Active</Badge>
                    </div>
                    <h3 className="text-base font-semibold text-foreground">
                      Ordinary Differential Equations
                    </h3>
                    <p className="font-serif text-sm leading-[1.65] text-muted-foreground">
                      First- and second-order linear equations, systems, phase portraits,
                      qualitative analysis. Foundation for classical mechanics, circuits,
                      and signal processing.
                    </p>
                  </div>

                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Prerequisite</p>
                    <div className="flex flex-wrap gap-1.5">
                      <Badge variant="ghost">Calculus I</Badge>
                      <Badge variant="ghost">Calculus II</Badge>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Unlocks</p>
                    <div className="flex flex-wrap gap-1.5">
                      <Badge variant="outline">Classical mechanics</Badge>
                      <Badge variant="outline">Signal processing</Badge>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Your progress</p>
                    <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                      <div className="h-full w-3/5 rounded-full bg-amber" />
                    </div>
                    <p className="text-xs text-muted-foreground">6 of 10 problems attempted</p>
                  </div>

                  <div className="flex flex-col gap-2">
                    <Button size="sm" className="w-full">Add to queue</Button>
                    <Button size="sm" variant="outline" className="w-full">Bookmark</Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Section>
      </div>
    </div>
  );
}

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Leaf, Target, Shield, Globe, Users, TrendingUp } from "lucide-react";

const sdgGoals = [
  {
    number: 14,
    title: "Life Below Water",
    description: "Conserve and sustainably use oceans, seas and marine resources",
    icon: Globe,
  },
  {
    number: 15,
    title: "Life on Land", 
    description: "Protect, restore and promote sustainable use of terrestrial ecosystems",
    icon: Leaf,
  },
  {
    number: 13,
    title: "Climate Action",
    description: "Take urgent action to combat climate change and its impacts",
    icon: Shield,
  },
];

const impactAreas = [
  {
    title: "Biodiversity Monitoring",
    description: "Non-invasive species detection from water, soil or sediment samples - no organism capture required. Surfaces rare, cryptic, and nocturnal taxa that traditional surveys routinely miss.",
    icon: Target,
    metrics: "Non-invasive sampling",
    color: "emerald",
  },
  {
    title: "Conservation Cross-Referencing",
    description: "Every detected taxon is automatically cross-referenced against GBIF occurrences and the IUCN Red List so users see conservation status alongside detections, not after the fact.",
    icon: Shield,
    metrics: "GBIF + IUCN integrated",
    color: "accent",
  },
  {
    title: "Reproducible Research",
    description: "Every analysis produces a signed provenance manifest - input hashes, tool versions, database versions, parameters, output hashes - so any result can be independently re-verified.",
    icon: TrendingUp,
    metrics: "Signed provenance",
    color: "muted",
  },
];

const ethicsPoints = [
  "Non-invasive sampling reduces ecological disturbance",
  "Open data sharing accelerates conservation research",
  "Democratized access to biodiversity monitoring tools",
  "Collaborative international research frameworks",
  "Ethical AI development with transparent methodologies",
];

export const ImpactSection = () => {
  return (
    <div className="space-y-12">
      {/* Impact Areas */}
      <section>
        <h2 className="text-3xl font-display font-bold mb-8 text-center">
          Environmental Impact
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {impactAreas.map((area) => (
            <Card key={area.title} className="p-6 glass hover-lift">
              <div className="flex items-center space-x-3 mb-4">
                <div className={`p-2 rounded-lg bg-${area.color}/10`}>
                  <area.icon className={`w-6 h-6 text-${area.color}`} />
                </div>
                <h3 className="text-xl font-display font-semibold">{area.title}</h3>
              </div>
              <p className="text-muted-foreground mb-4">{area.description}</p>
              <Badge variant="secondary" className="text-xs">
                {area.metrics}
              </Badge>
            </Card>
          ))}
        </div>
      </section>

      {/* SDG Alignment */}
      <section>
        <h2 className="text-3xl font-display font-bold mb-8 text-center">
          Supporting Sustainable Development Goals
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {sdgGoals.map((goal) => (
            <Card key={goal.number} className="p-6 glass hover-lift">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-emerald/10 rounded-lg flex items-center justify-center">
                    <span className="text-lg font-bold text-emerald">{goal.number}</span>
                  </div>
                </div>
                <div>
                  <h3 className="text-lg font-display font-semibold mb-2">{goal.title}</h3>
                  <p className="text-sm text-muted-foreground">{goal.description}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* Who benefits */}
      <section>
        <Card className="p-8 glass">
          <div className="text-center mb-6">
            <Users className="w-12 h-12 mx-auto text-accent mb-4" />
            <h2 className="text-3xl font-display font-bold mb-4">
              Who This Is For
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <h3 className="text-xl font-display font-semibold mb-4">Researchers & Labs</h3>
              <ul className="space-y-3 text-muted-foreground">
                <li className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-emerald rounded-full mt-2 flex-shrink-0"></div>
                  <span>One-command reproducible pipelines (fastp → vsearch UNOISE3 → SILVA/MIDORI2 → diversity metrics)</span>
                </li>
                <li className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-emerald rounded-full mt-2 flex-shrink-0"></div>
                  <span>Signed provenance manifests suitable for supplementary materials</span>
                </li>
                <li className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-emerald rounded-full mt-2 flex-shrink-0"></div>
                  <span>BIOM, Darwin Core Archive, and CSV exports</span>
                </li>
                <li className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-emerald rounded-full mt-2 flex-shrink-0"></div>
                  <span>Benchmark reports with committed, re-runnable scripts</span>
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-display font-semibold mb-4">Conservationists & Citizen Scientists</h3>
              <ul className="space-y-3 text-muted-foreground">
                <li className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-accent rounded-full mt-2 flex-shrink-0"></div>
                  <span>Upload a water/soil sample, get a plain-language conservation report</span>
                </li>
                <li className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-accent rounded-full mt-2 flex-shrink-0"></div>
                  <span>IUCN Red List status and legal protection flags on every detected taxon</span>
                </li>
                <li className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-accent rounded-full mt-2 flex-shrink-0"></div>
                  <span>Optional one-click submission to GBIF as a DNA-derived occurrence record</span>
                </li>
                <li className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-accent rounded-full mt-2 flex-shrink-0"></div>
                  <span>No bioinformatics expertise required</span>
                </li>
              </ul>
            </div>
          </div>
        </Card>
      </section>

      {/* Ethics & Responsibility */}
      <section>
        <Card className="p-8 bg-gradient-glass">
          <h2 className="text-3xl font-display font-bold mb-6 text-center">
            Ethical Considerations
          </h2>
          <div className="max-w-3xl mx-auto">
            <p className="text-lg text-muted-foreground mb-6 text-center">
              Our commitment to responsible research and ethical AI development
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {ethicsPoints.map((point, index) => (
                <div key={index} className="flex items-start space-x-3">
                  <div className="w-2 h-2 bg-emerald rounded-full mt-2 flex-shrink-0"></div>
                  <span className="text-sm">{point}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </section>

      {/* Call to Action */}
      <section className="text-center">
        <Card className="p-8 bg-gradient-hero text-white">
          <h2 className="text-3xl font-display font-bold mb-4">
            Open-Source. Reproducible. Built for the Real World.
          </h2>
          <p className="text-lg opacity-90 mb-6 max-w-2xl mx-auto">
            No mock data. No fake numbers. Every pipeline stage is real,
            every reference database is version-pinned, and every result
            ships with a provenance manifest you can verify yourself.
          </p>
          <div className="text-sm opacity-75">
            <p>MIT-licensed • Contributions welcome</p>
          </div>
        </Card>
      </section>
    </div>
  );
};
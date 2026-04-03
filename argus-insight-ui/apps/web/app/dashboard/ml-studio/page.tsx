"use client"

import { useState } from "react"
import { DashboardHeader } from "@/components/dashboard-header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import { FlaskConical, History, Workflow } from "lucide-react"
import { MLStudioWizard } from "@/features/ml-studio/components/ml-studio-wizard"
import { MLStudioExperiments } from "@/features/ml-studio/components/ml-studio-experiments"
import { MLStudioModeler } from "@/features/ml-studio/components/ml-studio-modeler"

export default function MLStudioPage() {
  const [activeTab, setActiveTab] = useState("wizard")

  return (
    <>
      <DashboardHeader title="ML Studio" />
      <div className="flex flex-1 flex-col p-4">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-1 flex-col">
          <TabsList>
            <TabsTrigger value="wizard">
              <FlaskConical className="mr-1.5 h-3.5 w-3.5" />
              Wizard
            </TabsTrigger>
            <TabsTrigger value="modeler">
              <Workflow className="mr-1.5 h-3.5 w-3.5" />
              Modeler
            </TabsTrigger>
            <TabsTrigger value="experiments">
              <History className="mr-1.5 h-3.5 w-3.5" />
              Experiments
            </TabsTrigger>
          </TabsList>

          <TabsContent value="wizard" className="mt-4 flex flex-1 flex-col">
            <MLStudioWizard />
          </TabsContent>

          <TabsContent value="modeler" className="mt-2 flex flex-1 flex-col">
            <MLStudioModeler onExecuted={() => setActiveTab("experiments")} />
          </TabsContent>

          <TabsContent value="experiments" className="mt-4 flex flex-1 flex-col">
            <MLStudioExperiments />
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}

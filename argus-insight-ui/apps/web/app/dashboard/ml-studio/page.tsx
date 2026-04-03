"use client"

import { DashboardHeader } from "@/components/dashboard-header"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@workspace/ui/components/tabs"
import { FlaskConical, History } from "lucide-react"
import { MLStudioWizard } from "@/features/ml-studio/components/ml-studio-wizard"
import { MLStudioExperiments } from "@/features/ml-studio/components/ml-studio-experiments"

export default function MLStudioPage() {
  return (
    <>
      <DashboardHeader title="ML Studio" />
      <div className="flex flex-1 flex-col p-4">
        <Tabs defaultValue="wizard" className="flex flex-1 flex-col">
          <TabsList>
            <TabsTrigger value="wizard">
              <FlaskConical className="mr-1.5 h-3.5 w-3.5" />
              Wizard
            </TabsTrigger>
            <TabsTrigger value="experiments">
              <History className="mr-1.5 h-3.5 w-3.5" />
              Experiments
            </TabsTrigger>
          </TabsList>

          <TabsContent value="wizard" className="mt-4">
            <MLStudioWizard />
          </TabsContent>

          <TabsContent value="experiments" className="mt-4 flex flex-1 flex-col">
            <MLStudioExperiments />
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}

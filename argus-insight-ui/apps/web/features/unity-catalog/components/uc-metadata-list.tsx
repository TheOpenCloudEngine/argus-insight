"use client"

import { formatTimestamp } from "../lib/format"

type MetadataItem = {
  label: string
  value: string | number | null | undefined
  render?: (val: string | number) => React.ReactNode
}

type UCMetadataListProps = {
  title: string
  items: MetadataItem[]
}

export function UCMetadataList({ title, items }: UCMetadataListProps) {
  return (
    <div className="space-y-3">
      <h4 className="text-sm font-semibold">{title}</h4>
      <dl className="space-y-2">
        {items.map((item) => {
          if (item.value == null) return null
          return (
            <div key={item.label}>
              <dt className="text-muted-foreground text-xs">{item.label}</dt>
              <dd className="text-sm">
                {item.render ? item.render(item.value) : String(item.value)}
              </dd>
            </div>
          )
        })}
      </dl>
    </div>
  )
}

export function UCTimestampMetadata({ createdAt, updatedAt }: { createdAt?: number | null; updatedAt?: number | null }) {
  return (
    <UCMetadataList
      title="Details"
      items={[
        { label: "Created at", value: createdAt, render: (v) => formatTimestamp(v as number) },
        { label: "Updated at", value: updatedAt, render: (v) => formatTimestamp(v as number) },
      ]}
    />
  )
}

export default function KubernetesLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="text-sm [&_code]:font-[family-name:var(--font-d2coding)] [&_.font-mono]:font-[family-name:var(--font-d2coding)] [&_pre]:font-[family-name:var(--font-d2coding)]">
      {children}
    </div>
  )
}

import { CircleAlert, Loader2 } from "lucide-react"
import { Toaster as Sonner, type ToasterProps } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="dark"
      position="bottom-right"
      className="toaster group"
      icons={{
        error: <CircleAlert className="size-4 text-danger" />,
        loading: <Loader2 className="size-4 animate-spin" />,
      }}
      toastOptions={{
        classNames: {
          toast:
            "!bg-surface-raised !border-border-strong !text-foreground !text-body !w-[360px] !rounded-lg !shadow-[0_8px_24px_rgba(0,0,0,0.45)]",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }

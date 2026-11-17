import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { buttonVariants } from "@/components/ui/button";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  body: string;
  confirmLabel: string;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
  cancelLabel?: string;
  confirmVariant?: "default" | "destructive";
  confirmTestId?: string;
};

/** Design section 5.23: focus starts on Cancel, Esc cancels. */
export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  onConfirm,
  onOpenChange,
  cancelLabel = "Cancelar",
  confirmVariant = "destructive",
  confirmTestId,
}: ConfirmDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="sm:max-w-[420px]">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-h3 font-medium">{title}</AlertDialogTitle>
          <AlertDialogDescription className="text-body text-foreground-soft">{body}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel autoFocus className={buttonVariants({ variant: "outline" })}>
            {cancelLabel}
          </AlertDialogCancel>
          <AlertDialogAction
            className={buttonVariants({ variant: confirmVariant })}
            data-variant={confirmVariant}
            data-testid={confirmTestId}
            onClick={onConfirm}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

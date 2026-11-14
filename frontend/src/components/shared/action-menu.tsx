"use client";

import * as React from "react";
import Link from "next/link";
import { Button } from "@/components/shared/button";
import { cn } from "@/lib/utils";

/**
 * A dropdown "Actions" menu anchored to its trigger button.
 *
 * The panel is rendered at a fixed position computed from the trigger's
 * bounding rect so it escapes any `overflow-x-auto` wrapper (e.g. table
 * containers) and stays on-screen near the viewport edge by growing
 * leftward from the trigger's right edge.
 *
 * Usage:
 *   <ActionMenu label="Actions">
 *     <ActionMenu.Link href="/books/1">Open book detail</ActionMenu.Link>
 *     <ActionMenu.Button onClick={doThing}>Do thing</ActionMenu.Button>
 *     <ActionMenu.Separator />
 *   </ActionMenu>
 *
 * Item clicks (buttons) close the menu automatically; links close on
 * navigation anyway but we close them too so the menu doesn't linger if
 * the navigation is intercepted.
 */

interface ActionMenuContextValue {
  close: () => void;
}

const ActionMenuContext = React.createContext<ActionMenuContextValue | null>(
  null,
);

function useActionMenuContext(): ActionMenuContextValue {
  const ctx = React.useContext(ActionMenuContext);
  if (!ctx) {
    throw new Error("ActionMenu items must be used within <ActionMenu>");
  }
  return ctx;
}

interface ActionMenuProps {
  children: React.ReactNode;
  /** Trigger label. */
  label?: string;
  disabled?: boolean;
  /** Visual style of the trigger. */
  variant?: "outline" | "ghost";
  /** Accessible name for the trigger if the label is ambiguous. */
  ariaLabel?: string;
}

export function ActionMenu({
  children,
  label = "Actions",
  disabled = false,
  variant = "outline",
  ariaLabel,
}: ActionMenuProps) {
  const [open, setOpen] = React.useState(false);
  const [menuPos, setMenuPos] = React.useState<{
    top: number;
    right: number;
  } | null>(null);
  const buttonRef = React.useRef<HTMLButtonElement | null>(null);
  const menuRef = React.useRef<HTMLDivElement | null>(null);

  const close = React.useCallback(() => setOpen(false), []);

  React.useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        menuRef.current &&
        !menuRef.current.contains(target) &&
        buttonRef.current &&
        !buttonRef.current.contains(target)
      ) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const openMenu = () => {
    if (open) {
      setOpen(false);
      return;
    }
    const btn = buttonRef.current;
    if (btn) {
      const rect = btn.getBoundingClientRect();
      setMenuPos({
        top: rect.bottom + 4,
        right: window.innerWidth - rect.right,
      });
    }
    setOpen(true);
  };

  const contextValue = React.useMemo(() => ({ close }), [close]);

  return (
    <>
      <Button
        ref={buttonRef}
        variant={variant}
        size="sm"
        onClick={openMenu}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={ariaLabel}
        disabled={disabled}
      >
        {label}
        <svg
          viewBox="0 0 20 20"
          fill="currentColor"
          className="size-3.5"
          aria-hidden="true"
        >
          <path d="M5.23 7.21a.75.75 0 011.06.02L10 11.06l3.71-3.83a.75.75 0 111.08 1.04l-4.25 4.39a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z" />
        </svg>
      </Button>
      {open && menuPos && (
        <div
          ref={menuRef}
          role="menu"
          aria-label={ariaLabel ?? label}
          style={{ top: menuPos.top, right: menuPos.right }}
          className="fixed w-56 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)] py-1 text-left z-50 animate-fade-in"
        >
          <ActionMenuContext.Provider value={contextValue}>
            {children}
          </ActionMenuContext.Provider>
        </div>
      )}
    </>
  );
}

export function MenuLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  const { close } = useActionMenuContext();
  return (
    <Link
      href={href}
      role="menuitem"
      onClick={close}
      className="block px-3 py-2 text-[length:var(--text-sm)] text-[var(--text)] hover:bg-[var(--surface-sunken)] focus-visible:bg-[var(--surface-sunken)] focus:outline-none"
    >
      {children}
    </Link>
  );
}

export function MenuButton({
  onClick,
  children,
  danger,
  disabled,
}: {
  onClick: () => void;
  children: React.ReactNode;
  danger?: boolean;
  disabled?: boolean;
}) {
  const { close } = useActionMenuContext();
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={() => {
        close();
        onClick();
      }}
      className={cn(
        "block w-full text-left px-3 py-2 text-[length:var(--text-sm)] hover:bg-[var(--surface-sunken)] focus-visible:bg-[var(--surface-sunken)] focus:outline-none disabled:opacity-50 disabled:pointer-events-none",
        danger
          ? "text-[var(--danger-700)] dark:text-[var(--danger-300)]"
          : "text-[var(--text)]",
      )}
    >
      {children}
    </button>
  );
}

export function MenuSeparator() {
  return <div className="my-1 border-t border-[var(--border)]" />;
}

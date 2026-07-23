/**
 * ARIA workspace — the left rail.
 *
 * Conversations first (the farmer's own history), then the day's operational
 * shortcuts: what's due, what's overdue. History is searchable, pinnable and
 * renamable in place; the operational counts link the farmer straight to the
 * thing that needs attention.
 *
 * Everything reads from client-side history (conversationStore) and the same
 * deterministic schedule endpoint the snapshot uses. No LLM anywhere.
 */
import { useState } from "react";
import {
  Archive,
  Check,
  MoreVertical,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Search,
  Syringe,
  Trash2,
  X,
} from "lucide-react";
import type { StoredConversation } from "./conversationStore";
import { cn } from "@/lib/cn";

export function AriaWorkspaceSidebar({
  conversations,
  activeId,
  dueVaccinations,
  onSelect,
  onNew,
  onSearch,
  onRename,
  onTogglePin,
  onToggleArchive,
  onDelete,
  onVaccinationsClick,
  className,
}: {
  conversations: StoredConversation[];
  activeId: string | null;
  dueVaccinations: number;
  onSelect: (id: string) => void;
  onNew: () => void;
  onSearch: (q: string) => void;
  onRename: (id: string, title: string) => void;
  onTogglePin: (id: string) => void;
  onToggleArchive: (id: string) => void;
  onDelete: (id: string) => void;
  onVaccinationsClick: () => void;
  className?: string;
}) {
  const [query, setQuery] = useState("");
  const active = conversations.filter((c) => !c.archived);
  const archived = conversations.filter((c) => c.archived);

  return (
    <div className={cn("flex h-full flex-col", className)}>
      <div className="flex items-center gap-2 p-3">
        <button
          type="button"
          onClick={onNew}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand-600 px-3 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-1 dark:focus-visible:ring-offset-gray-900"
        >
          <Plus className="h-4 w-4" aria-hidden />
          New conversation
        </button>
      </div>

      {/* Operational shortcuts */}
      <div className="px-3 pb-2">
        <button
          type="button"
          onClick={onVaccinationsClick}
          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-gray-600 transition-colors hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/[0.06]"
        >
          <Syringe className="h-4 w-4 text-brand-500" aria-hidden />
          <span className="flex-1 text-left">Vaccinations due</span>
          {dueVaccinations > 0 && (
            <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-semibold text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
              {dueVaccinations}
            </span>
          )}
        </button>
      </div>

      {/* Search */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400" aria-hidden />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              onSearch(e.target.value);
            }}
            placeholder="Search conversations"
            aria-label="Search conversations"
            className="w-full rounded-lg border border-gray-200 bg-white py-1.5 pl-8 pr-2 text-sm text-gray-900 outline-none placeholder:text-gray-400 focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.03] dark:text-white"
          />
        </div>
      </div>

      {/* Conversation list */}
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {active.length === 0 && archived.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-gray-400 dark:text-gray-500">
            No conversations yet. Start by telling ARIA what happened on the farm today.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {active.map((c) => (
              <ConversationRow
                key={c.id}
                conversation={c}
                active={c.id === activeId}
                onSelect={onSelect}
                onRename={onRename}
                onTogglePin={onTogglePin}
                onToggleArchive={onToggleArchive}
                onDelete={onDelete}
              />
            ))}
          </ul>
        )}

        {archived.length > 0 && (
          <>
            <p className="px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">
              Archived
            </p>
            <ul className="space-y-0.5 opacity-70">
              {archived.map((c) => (
                <ConversationRow
                  key={c.id}
                  conversation={c}
                  active={c.id === activeId}
                  onSelect={onSelect}
                  onRename={onRename}
                  onTogglePin={onTogglePin}
                  onToggleArchive={onToggleArchive}
                  onDelete={onDelete}
                />
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}

function ConversationRow({
  conversation,
  active,
  onSelect,
  onRename,
  onTogglePin,
  onToggleArchive,
  onDelete,
}: {
  conversation: StoredConversation;
  active: boolean;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onTogglePin: (id: string) => void;
  onToggleArchive: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(conversation.title);

  const commitRename = () => {
    const t = draft.trim();
    if (t) onRename(conversation.id, t);
    setEditing(false);
  };

  if (editing) {
    return (
      <li className="flex items-center gap-1 rounded-lg bg-gray-100 px-2 py-1 dark:bg-white/[0.06]">
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitRename();
            if (e.key === "Escape") setEditing(false);
          }}
          aria-label="Rename conversation"
          className="min-w-0 flex-1 bg-transparent text-sm text-gray-900 outline-none dark:text-white"
        />
        <button type="button" onClick={commitRename} aria-label="Save name" className="p-1 text-brand-600">
          <Check className="h-3.5 w-3.5" />
        </button>
        <button type="button" onClick={() => setEditing(false)} aria-label="Cancel" className="p-1 text-gray-400">
          <X className="h-3.5 w-3.5" />
        </button>
      </li>
    );
  }

  return (
    <li className="group relative">
      <button
        type="button"
        onClick={() => onSelect(conversation.id)}
        className={cn(
          "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors",
          active
            ? "bg-brand-50 text-brand-800 dark:bg-brand-500/15 dark:text-brand-200"
            : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/[0.06]",
        )}
      >
        {conversation.pinned && <Pin className="h-3 w-3 shrink-0 text-brand-500" aria-hidden />}
        <span className="min-w-0 flex-1 truncate">{conversation.title}</span>
      </button>

      <button
        type="button"
        onClick={() => setMenuOpen((o) => !o)}
        aria-label="Conversation options"
        className="absolute right-1 top-1/2 -translate-y-1/2 rounded p-1.5 text-gray-400 opacity-0 transition-opacity hover:bg-gray-200 group-hover:opacity-100 focus-visible:opacity-100 dark:hover:bg-white/10"
      >
        <MoreVertical className="h-3.5 w-3.5" aria-hidden />
      </button>

      {menuOpen && (
        <>
          <button
            type="button"
            aria-hidden
            tabIndex={-1}
            className="fixed inset-0 z-10 cursor-default"
            onClick={() => setMenuOpen(false)}
          />
          <div className="absolute right-1 top-9 z-20 w-40 overflow-hidden rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-white/10 dark:bg-gray-800">
            <MenuItem
              icon={conversation.pinned ? PinOff : Pin}
              label={conversation.pinned ? "Unpin" : "Pin"}
              onClick={() => {
                onTogglePin(conversation.id);
                setMenuOpen(false);
              }}
            />
            <MenuItem
              icon={Pencil}
              label="Rename"
              onClick={() => {
                setDraft(conversation.title);
                setEditing(true);
                setMenuOpen(false);
              }}
            />
            <MenuItem
              icon={Archive}
              label={conversation.archived ? "Unarchive" : "Archive"}
              onClick={() => {
                onToggleArchive(conversation.id);
                setMenuOpen(false);
              }}
            />
            <MenuItem
              icon={Trash2}
              label="Delete"
              destructive
              onClick={() => {
                onDelete(conversation.id);
                setMenuOpen(false);
              }}
            />
          </div>
        </>
      )}
    </li>
  );
}

function MenuItem({
  icon: Icon,
  label,
  onClick,
  destructive = false,
}: {
  icon: typeof Pin;
  label: string;
  onClick: () => void;
  destructive?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors",
        destructive
          ? "text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
          : "text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-white/[0.06]",
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {label}
    </button>
  );
}

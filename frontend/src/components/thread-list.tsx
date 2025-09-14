import type { FC } from "react";
import { useEffect, useRef, useState } from 'react';
import { ThreadListPrimitive } from "@assistant-ui/react";
import { ArchiveIcon, PlusIcon, PencilIcon, CheckIcon, XIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/tooltip-icon-button";
import { dreamFarmAPI } from '@/services/api';
import { dreamFarmChatAdapter } from '@/services/chatAdapter';

interface ServerThreadMeta {
  thread_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export const ThreadList: FC = () => {
  return (
    <ThreadListPrimitive.Root className="text-foreground flex flex-col items-stretch gap-1.5">
      <ThreadListNew />
      <ThreadListItems />
    </ThreadListPrimitive.Root>
  );
};

const ThreadListNew: FC = () => {
  // We handle creation manually so a distinct backend thread row is created immediately
  const [creating, setCreating] = useState(false);
  const handleNew = async () => {
    if (creating) return;
    try {
      setCreating(true);
      // Reset adapter so subsequent messages use fresh thread id
      dreamFarmChatAdapter.reset();
      // Proactively create empty thread row now so it appears in list even before first message
      const title = `New Chat ${new Date().toLocaleTimeString()}`;
  const res = await dreamFarmAPI.createThread(title);
  // Immediately set adapter thread id so first message goes to this thread
  dreamFarmChatAdapter.setThreadId(res.thread_id);
  // Broadcast creation & implicit selection so App & list update
  window.dispatchEvent(new CustomEvent('df-thread-created', { detail: res }));
  window.dispatchEvent(new CustomEvent('df-thread-selected', { detail: res }));
    } catch (e) {
      // Silently ignore for now; could show toast if toast system present
    } finally {
      setCreating(false);
    }
  };
  return (
    <Button onClick={handleNew} disabled={creating} className="data-[active]:bg-muted hover:bg-muted flex items-center justify-start gap-1 rounded-lg px-2.5 py-2 text-start" variant="ghost">
      <PlusIcon />
      {creating ? 'Creating…' : 'New Thread'}
    </Button>
  );
};

const ThreadListItems: FC = () => {
  const [serverThreads, setServerThreads] = useState<ServerThreadMeta[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const retryCount = useRef(0);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const data = await dreamFarmAPI.listThreads(10, 0);
      setServerThreads(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load threads');
      // Retry a few times in case auth token wasn't ready yet
      if (retryCount.current < 5) {
        retryCount.current += 1;
        setTimeout(load, 500 * retryCount.current); // incremental backoff
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(() => { if (!loading) load(); }, 60000);
    // Listen for newly created thread events
    const onCreated = (e: Event) => {
      const detail: any = (e as CustomEvent).detail;
      if (!detail?.thread_id) return;
      setServerThreads(prev => [{
        thread_id: detail.thread_id,
        title: detail.title || 'Untitled',
        created_at: detail.created_at || new Date().toISOString(),
        updated_at: detail.updated_at || new Date().toISOString(),
        message_count: 0,
      }, ...prev.filter(t => t.thread_id !== detail.thread_id)]);
    };
    window.addEventListener('df-thread-created', onCreated);
    // Refresh when window gains focus (helps after auth redirect)
    const onFocus = () => { if (!loading) load(); };
    window.addEventListener('focus', onFocus);
  return () => { clearInterval(interval); window.removeEventListener('df-thread-created', onCreated); window.removeEventListener('focus', onFocus); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSelect = (t: ServerThreadMeta) => {
    setActiveThreadId(t.thread_id);
    dreamFarmChatAdapter.setThreadId(t.thread_id);
  // Preload messages immediately
  dreamFarmChatAdapter.preloadMessages(t.thread_id);
    window.dispatchEvent(new CustomEvent('df-thread-selected', { detail: t }));
  };

  const handleDelete = async (t: ServerThreadMeta) => {
    const prev = serverThreads;
    setServerThreads(s => s.filter(x => x.thread_id !== t.thread_id));
    try { await dreamFarmAPI.deleteThread(t.thread_id); }
    catch { setServerThreads(prev); }
  };

  const startEdit = (t: ServerThreadMeta) => {
    setEditingId(t.thread_id);
    setEditValue(t.title);
  };
  const cancelEdit = () => { setEditingId(null); setEditValue(""); };
  const submitEdit = async (t: ServerThreadMeta) => {
    const newTitle = editValue.trim();
    if (!newTitle || newTitle === t.title) { cancelEdit(); return; }
    // optimistic update
    setServerThreads(list => list.map(x => x.thread_id === t.thread_id ? { ...x, title: newTitle } : x));
    try {
      await dreamFarmAPI.renameThread(t.thread_id, newTitle);
    } catch {
      // rollback
      setServerThreads(list => list.map(x => x.thread_id === t.thread_id ? { ...x, title: t.title } : x));
    } finally { cancelEdit(); }
  };

  return (
    <div className="flex flex-col gap-1">
      {loading && <div className="text-xs text-muted-foreground px-2">Loading…</div>}
      {error && <div className="text-xs text-destructive px-2">{error}</div>}
      {serverThreads.map(t => {
        const isActive = t.thread_id === activeThreadId;
        const editing = editingId === t.thread_id;
        return (
          <div
            key={t.thread_id}
            className={`flex items-center gap-2 rounded-lg px-2 py-1 group ${isActive ? 'bg-muted' : 'hover:bg-muted/60'}`}
            title={t.title}
            onClick={() => { if (!editing) handleSelect(t); }}
          >
            {editing ? (
              <input
                autoFocus
                value={editValue}
                onChange={e => setEditValue(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') submitEdit(t); if (e.key === 'Escape') cancelEdit(); }}
                className="flex-grow text-sm bg-background border rounded px-2 py-1"
              />
            ) : (
              <div className="flex-grow text-left text-sm truncate">{t.title || 'Untitled'}</div>
            )}
            {editing ? (
              <div className="flex items-center gap-1">
                <TooltipIconButton tooltip="Save" variant="ghost" onClick={(e) => { e.stopPropagation(); submitEdit(t); }}>
                  <CheckIcon size={16} />
                </TooltipIconButton>
                <TooltipIconButton tooltip="Cancel" variant="ghost" onClick={(e) => { e.stopPropagation(); cancelEdit(); }}>
                  <XIcon size={16} />
                </TooltipIconButton>
              </div>
            ) : (
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <TooltipIconButton tooltip="Rename" variant="ghost" onClick={(e) => { e.stopPropagation(); startEdit(t); }}>
                  <PencilIcon size={16} />
                </TooltipIconButton>
                <TooltipIconButton tooltip="Delete" variant="ghost" onClick={(e) => { e.stopPropagation(); handleDelete(t); }}>
                  <ArchiveIcon size={16} />
                </TooltipIconButton>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

// Removed internal ThreadListPrimitive.Items usage to avoid conflict with custom server-backed list.

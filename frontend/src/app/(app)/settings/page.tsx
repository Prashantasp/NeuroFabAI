"use client";

/**
 * Settings.
 *
 * Previously a static page of hardcoded text that also misreported the stack
 * ("SQLite", "NetworkX (Local In-Memory)") while the app ran on PostgreSQL and
 * Neo4j. Every section here reads or writes real state.
 */

import {
  Loader2,
  Server,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ThemeSelector } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState, ErrorState, InlineError } from "@/components/ui/states";
import { StatusPill } from "@/components/ui/status";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/contexts/AuthContext";
import { useAction, useAsync } from "@/hooks/use-async";
import { useResetOnChange } from "@/hooks/use-reset-on-change";
import {
  ApiError,
  api,
  errorMessage,
  type WorkspaceMember,
  type WorkspaceRole,
} from "@/lib/api";
import { formatRelativeTime, initialsOf } from "@/lib/format";
import { cn } from "@/lib/utils";

const SECTIONS = [
  { id: "profile", label: "Profile" },
  { id: "security", label: "Security" },
  { id: "workspace", label: "Workspace" },
  { id: "members", label: "Members" },
  { id: "appearance", label: "Appearance" },
  { id: "system", label: "System" },
] as const;

export default function SettingsPage() {
  const [section, setSection] = useState<(typeof SECTIONS)[number]["id"]>("profile");

  return (
    <div className="mx-auto w-full max-w-[1100px] space-y-5 p-4 sm:p-6">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">Settings</h2>
        <p className="text-sm text-muted-foreground">
          Manage your account, workspace, and appearance.
        </p>
      </header>

      <div className="grid gap-5 lg:grid-cols-[13rem_minmax(0,1fr)]">
        {/* Tabs scroll horizontally on small screens rather than wrapping into
            an unusable stack. */}
        <nav
          aria-label="Settings sections"
          className="-mx-4 flex gap-1 overflow-x-auto no-scrollbar px-4 lg:mx-0 lg:flex-col lg:px-0"
        >
          {SECTIONS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSection(item.id)}
              aria-current={section === item.id ? "page" : undefined}
              className={cn(
                "shrink-0 rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors",
                section === item.id
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
              )}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="min-w-0">
          {section === "profile" && <ProfileSection />}
          {section === "security" && <SecuritySection />}
          {section === "workspace" && <WorkspaceSection />}
          {section === "members" && <MembersSection />}
          {section === "appearance" && <AppearanceSection />}
          {section === "system" && <SystemSection />}
        </div>
      </div>
    </div>
  );
}

function Card({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border bg-card">
      <div className="border-b px-5 py-4">
        <h3 className="text-sm font-semibold">{title}</h3>
        {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
      </div>
      <div className="space-y-4 p-5">{children}</div>
      {footer && <div className="flex justify-end border-t px-5 py-3">{footer}</div>}
    </section>
  );
}

function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      {children}
      {error ? (
        <InlineError message={error} />
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

const inputClass =
  "h-9 w-full rounded-lg border bg-background px-3 text-sm outline-none transition-colors focus-visible:border-ring disabled:opacity-60";

/* -------------------------------------------------------------------------- */

function ProfileSection() {
  const { user, setUser } = useAuth();
  const toast = useToast();

  const [fullName, setFullName] = useState("");
  const [company, setCompany] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Re-seed the form when the underlying profile changes (e.g. after a save
  // elsewhere), without an effect that would briefly show stale values.
  useResetOnChange(user, () => {
    setFullName(user?.full_name ?? "");
    setCompany(user?.company ?? "");
  });

  const { run: save, isPending } = useAction(async () => {
    setError(null);
    try {
      const updated = await api.updateProfile({
        full_name: fullName.trim(),
        company: company.trim(),
      });
      setUser(updated);
      toast.success("Profile updated");
    } catch (err) {
      setError(errorMessage(err));
    }
  });

  const isDirty =
    fullName.trim() !== (user?.full_name ?? "") || company.trim() !== (user?.company ?? "");

  return (
    <Card
      title="Profile"
      description="How you appear across NeuroFab."
      footer={
        <Button onClick={() => void save()} disabled={isPending || !isDirty}>
          {isPending && <Loader2 className="size-3.5 animate-spin" />}
          Save changes
        </Button>
      }
    >
      <div className="flex items-center gap-3">
        <span
          className="flex size-11 items-center justify-center rounded-full bg-primary/12 text-sm font-semibold text-primary"
          aria-hidden
        >
          {initialsOf(user?.full_name ?? user?.email)}
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{user?.email}</p>
          <p className="text-xs text-muted-foreground">
            {user?.role} · joined {formatRelativeTime(user?.created_at)}
          </p>
        </div>
      </div>

      <Field id="full-name" label="Full name">
        <input
          id="full-name"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          maxLength={120}
          className={inputClass}
        />
      </Field>

      <Field id="company" label="Company" hint="Optional.">
        <input
          id="company"
          value={company}
          onChange={(event) => setCompany(event.target.value)}
          maxLength={120}
          className={inputClass}
        />
      </Field>

      <Field id="email" label="Email" hint="Contact an administrator to change your email.">
        <input id="email" value={user?.email ?? ""} disabled className={inputClass} />
      </Field>

      {error && <InlineError message={error} />}
    </Card>
  );
}

function SecuritySection() {
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { run: submit, isPending } = useAction(async () => {
    setError(null);
    if (next !== confirm) {
      setError("The new passwords do not match.");
      return;
    }
    try {
      await api.changePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      toast.success("Password updated", {
        description: "Your other sessions have been signed out.",
      });
    } catch (err) {
      // Surface the server's field-level message where there is one.
      setError(
        err instanceof ApiError && err.fieldErrors.length > 0
          ? err.fieldErrors[0].message
          : errorMessage(err),
      );
    }
  });

  const canSubmit = current.length > 0 && next.length > 0 && confirm.length > 0;

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <Card
        title="Change password"
        description="Choosing a new password signs out every other session."
        footer={
          <Button type="submit" disabled={isPending || !canSubmit}>
            {isPending && <Loader2 className="size-3.5 animate-spin" />}
            Update password
          </Button>
        }
      >
        <Field id="current-password" label="Current password">
          <input
            id="current-password"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            className={inputClass}
          />
        </Field>

        <Field
          id="new-password"
          label="New password"
          hint="At least 10 characters, with upper and lower case letters and a number."
        >
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(event) => setNext(event.target.value)}
            className={inputClass}
          />
        </Field>

        <Field id="confirm-password" label="Confirm new password" error={error ?? undefined}>
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            className={inputClass}
          />
        </Field>
      </Card>
    </form>
  );
}

function WorkspaceSection() {
  const { activeWorkspace, refreshWorkspaces, workspaces } = useAuth();
  const toast = useToast();
  const router = useRouter();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useResetOnChange(activeWorkspace, () => {
    setName(activeWorkspace?.name ?? "");
    setDescription(activeWorkspace?.description ?? "");
  });

  const isAdmin = activeWorkspace?.role === "OWNER" || activeWorkspace?.role === "ADMIN";
  const isOwner = activeWorkspace?.role === "OWNER";
  const isLastWorkspace = workspaces.length <= 1;

  const { run: save, isPending } = useAction(async () => {
    try {
      await api.updateWorkspace({ name: name.trim(), description: description.trim() });
      await refreshWorkspaces();
      toast.success("Workspace updated");
    } catch (error) {
      toast.error("Could not update the workspace", { description: errorMessage(error) });
    }
  });

  const { run: remove, isPending: isDeleting } = useAction(async () => {
    try {
      await api.deleteWorkspace();
      // Reloading the list also reselects an active workspace, so the app is
      // never left pointing at the workspace that was just deleted.
      await refreshWorkspaces();
      toast.success("Workspace deleted");
      router.push("/dashboard");
    } catch (error) {
      toast.error("Could not delete the workspace", { description: errorMessage(error) });
    }
  });

  if (!activeWorkspace) {
    return <EmptyState icon={Users} title="No workspace selected" />;
  }

  return (
    <div className="space-y-5">
      <Card
        title="Workspace details"
        description={isAdmin ? undefined : "Only owners and admins can change these."}
        footer={
          isAdmin ? (
            <Button
              onClick={() => void save()}
              disabled={
                isPending ||
                !name.trim() ||
                (name.trim() === activeWorkspace.name &&
                  description.trim() === (activeWorkspace.description ?? ""))
              }
            >
              {isPending && <Loader2 className="size-3.5 animate-spin" />}
              Save changes
            </Button>
          ) : undefined
        }
      >
        <Field id="workspace-name" label="Name">
          <input
            id="workspace-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={!isAdmin}
            maxLength={120}
            className={inputClass}
          />
        </Field>

        <Field id="workspace-description" label="Description" hint="Optional.">
          <textarea
            id="workspace-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            disabled={!isAdmin}
            rows={3}
            maxLength={1000}
            className="w-full resize-y rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus-visible:border-ring disabled:opacity-60"
          />
        </Field>

        <dl className="grid grid-cols-2 gap-3 border-t pt-4 text-sm">
          <div>
            <dt className="text-muted-foreground">Documents</dt>
            <dd className="tabular font-medium">{activeWorkspace.document_count}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Members</dt>
            <dd className="tabular font-medium">{activeWorkspace.member_count}</dd>
          </div>
        </dl>
      </Card>

      {isOwner && (
        <section className="rounded-xl border border-danger/25 bg-card">
          <div className="border-b border-danger/25 px-5 py-4">
            <h3 className="text-sm font-semibold text-danger">Danger zone</h3>
          </div>
          <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-sm font-medium">Delete this workspace</p>
              <p className="text-sm text-muted-foreground">
                {isLastWorkspace
                  ? "You cannot delete your only workspace. Create another one first."
                  : "Permanently removes every document, indexed passage, and graph entity."}
              </p>
            </div>
            <Button
              variant="destructive"
              onClick={() => setConfirmingDelete(true)}
              disabled={isDeleting || isLastWorkspace}
              className="shrink-0"
            >
              <Trash2 className="size-4" />
              Delete workspace
            </Button>
          </div>
        </section>
      )}

      <ConfirmDialog
        open={confirmingDelete}
        title={`Delete "${activeWorkspace.name}"?`}
        description={`All ${activeWorkspace.document_count} document(s), their indexed text, and every extracted entity will be permanently deleted. This cannot be undone.`}
        confirmLabel="Delete workspace"
        destructive
        onConfirm={() => {
          setConfirmingDelete(false);
          void remove();
        }}
        onCancel={() => setConfirmingDelete(false)}
      />
    </div>
  );
}

function MembersSection() {
  const { activeWorkspace, user } = useAuth();
  const toast = useToast();
  const members = useAsync(() => api.listMembers(), [activeWorkspace?.id], {
    enabled: Boolean(activeWorkspace),
  });

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<WorkspaceRole>("MEMBER");
  const [pendingRemove, setPendingRemove] = useState<WorkspaceMember | null>(null);

  const isAdmin = activeWorkspace?.role === "OWNER" || activeWorkspace?.role === "ADMIN";

  const { run: invite, isPending } = useAction(async () => {
    try {
      await api.addMember(email.trim(), role);
      setEmail("");
      await members.reload();
      toast.success("Member added");
    } catch (error) {
      toast.error("Could not add that member", { description: errorMessage(error) });
    }
  });

  const changeRole = async (member: WorkspaceMember, nextRole: WorkspaceRole) => {
    try {
      await api.updateMemberRole(member.user_id, nextRole);
      await members.reload();
      toast.success(`${member.email} is now ${nextRole.toLowerCase()}`);
    } catch (error) {
      toast.error("Could not change the role", { description: errorMessage(error) });
    }
  };

  const removeMember = async () => {
    if (!pendingRemove) return;
    const target = pendingRemove;
    setPendingRemove(null);
    try {
      await api.removeMember(target.user_id);
      await members.reload();
      toast.success(`${target.email} removed`);
    } catch (error) {
      toast.error("Could not remove that member", { description: errorMessage(error) });
    }
  };

  return (
    <div className="space-y-5">
      {isAdmin && (
        <Card
          title="Add a member"
          description="They need an existing NeuroFab account. Adding them grants access to every document in this workspace."
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void invite();
            }}
            className="flex flex-col gap-2 sm:flex-row"
          >
            <div className="flex-1">
              <label htmlFor="member-email" className="sr-only">
                Email address
              </label>
              <input
                id="member-email"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="colleague@company.com"
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="member-role" className="sr-only">
                Role
              </label>
              <select
                id="member-role"
                value={role}
                onChange={(event) => setRole(event.target.value as WorkspaceRole)}
                className={cn(inputClass, "sm:w-32")}
              >
                <option value="VIEWER">Viewer</option>
                <option value="MEMBER">Member</option>
                <option value="ADMIN">Admin</option>
              </select>
            </div>
            <Button type="submit" disabled={isPending || !email.trim()}>
              {isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <UserPlus className="size-4" />
              )}
              Add
            </Button>
          </form>
        </Card>
      )}

      <Card title="Members" description={`${members.data?.length ?? 0} with access.`}>
        {members.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="h-12 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : members.error ? (
          <ErrorState compact message={members.error} onRetry={members.reload} />
        ) : (
          <ul className="divide-y">
            {(members.data ?? []).map((member) => {
              const isSelf = member.user_id === user?.id;
              const isWorkspaceOwner = member.role === "OWNER";
              return (
                <li key={member.user_id} className="flex items-center gap-3 py-3 first:pt-0">
                  <span
                    className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold"
                    aria-hidden
                  >
                    {initialsOf(member.full_name ?? member.email)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {member.full_name ?? member.email}
                      {isSelf && <span className="ml-1.5 text-muted-foreground">(you)</span>}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">{member.email}</p>
                  </div>

                  {isAdmin && !isWorkspaceOwner ? (
                    <>
                      <label className="sr-only" htmlFor={`role-${member.user_id}`}>
                        Role for {member.email}
                      </label>
                      <select
                        id={`role-${member.user_id}`}
                        value={member.role}
                        onChange={(event) =>
                          void changeRole(member, event.target.value as WorkspaceRole)
                        }
                        className="h-8 rounded-md border bg-background px-2 text-xs outline-none focus-visible:border-ring"
                      >
                        <option value="VIEWER">Viewer</option>
                        <option value="MEMBER">Member</option>
                        <option value="ADMIN">Admin</option>
                      </select>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setPendingRemove(member)}
                        aria-label={`Remove ${member.email}`}
                        className="text-muted-foreground hover:bg-danger-soft hover:text-danger"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </>
                  ) : (
                    <span className="shrink-0 rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                      {member.role.toLowerCase()}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <ConfirmDialog
        open={Boolean(pendingRemove)}
        title="Remove this member?"
        description={
          pendingRemove
            ? `${pendingRemove.email} will immediately lose access to this workspace and its documents.`
            : ""
        }
        confirmLabel="Remove"
        destructive
        onConfirm={removeMember}
        onCancel={() => setPendingRemove(null)}
      />
    </div>
  );
}

function AppearanceSection() {
  return (
    <Card title="Appearance" description="Applies to this browser.">
      <div className="space-y-2">
        <p className="text-sm font-medium">Theme</p>
        <ThemeSelector />
      </div>
    </Card>
  );
}

function SystemSection() {
  const status = useAsync((signal) => api.systemStatus(signal), [], {
    refreshInterval: 30_000,
  });

  return (
    <div className="space-y-5">
      <Card title="Service status" description="Live health of every backend dependency.">
        {status.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-12 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : status.error ? (
          <ErrorState compact message={status.error} onRetry={status.reload} />
        ) : (
          <ul className="space-y-2">
            {(status.data?.components ?? []).map((component) => (
              <li
                key={component.name}
                className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <Server className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{component.name}</p>
                    <p className="truncate font-mono text-xs text-muted-foreground">
                      {component.detail}
                    </p>
                  </div>
                </div>
                <StatusPill
                  label={component.online ? "Online" : "Offline"}
                  tone={component.online ? "ok" : "danger"}
                  size="sm"
                />
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Models" description="Configured server-side. API keys are never sent to the browser.">
        <dl className="space-y-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted-foreground">Reasoning</dt>
            <dd className="truncate font-mono text-xs">
              {status.data?.models.reasoning ?? "Not configured"}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted-foreground">Embedding</dt>
            <dd className="truncate font-mono text-xs">
              {status.data?.models.embedding ?? "—"}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-muted-foreground">Vector dimension</dt>
            <dd className="tabular font-mono text-xs">
              {status.data?.models.embedding_dimension ?? "—"}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3 border-t pt-3">
            <dt className="text-muted-foreground">Environment</dt>
            <dd className="font-mono text-xs">
              {status.data?.environment} · v{status.data?.version}
            </dd>
          </div>
        </dl>
      </Card>

      <div className="flex items-start gap-2.5 rounded-lg border bg-card p-4 text-sm text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-ok" aria-hidden />
        <p>
          Documents, indexed passages, and graph entities are isolated per workspace. Every
          request is authorised server-side against your membership.
        </p>
      </div>
    </div>
  );
}

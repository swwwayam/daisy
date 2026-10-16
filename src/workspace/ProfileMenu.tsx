import { useEffect, useRef, useState, type FormEvent } from "react";
import { authClient } from "../services/auth";

export function ProfileMenu({ onSignOut }: { onSignOut: () => void | Promise<void> }) {
  const { data: session } = authClient.useSession();
  const user = session?.user;
  if (!user) return null;
  return <ProfileMenuView user={user} onSignOut={onSignOut} onSave={async name => {
    const result = await authClient.updateUser({ name });
    if (result.error) throw new Error(result.error.message || "Profile update failed.");
  }} />;
}

export function ProfileMenuView({ user, onSignOut, onSave }: { user: { name: string; email: string; emailVerified: boolean; createdAt: Date | string }; onSignOut: () => void | Promise<void>; onSave: (name: string) => Promise<void> }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState(user?.name ?? "");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { setName(user?.name ?? ""); }, [user?.name]);
  const initials = (user.name || user.email || "U").split(/\s+/).slice(0, 2).map(part => part[0]).join("").toUpperCase();
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setNotice(""); setError("");
    try {
      await onSave(name.trim());
      setNotice("Your profile has been updated.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Profile update failed. Try again."); }
    finally { setBusy(false); }
  }
  async function signOut() {
    setBusy(true); setError("");
    try { await onSignOut(); dialog.current?.close(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Sign out failed. Try again."); }
    finally { setBusy(false); }
  }
  return <>
    <button className="pill pill-ghost profile-trigger" aria-haspopup="dialog" onClick={() => { setError(""); setNotice(""); dialog.current?.showModal(); }}><span className="profile-avatar" aria-hidden="true">{initials}</span><span>Profile</span></button>
    <dialog ref={dialog} className="profile-dialog" aria-labelledby="profile-title" onClick={event => { if (event.target === dialog.current && !busy) dialog.current.close(); }} onCancel={event => { if (busy) event.preventDefault(); }}>
      <div className="profile-heading"><h2 id="profile-title">Your profile</h2><button className="pill pill-ghost" disabled={busy} onClick={() => dialog.current?.close()}>Close</button></div>
      <div className="profile-identity"><span className="profile-avatar large" aria-hidden="true">{initials}</span><div><strong>{user.name || "DAISY user"}</strong><p>{user.email}</p></div></div>
      <dl className="profile-facts"><div><dt>Email status</dt><dd>{user.emailVerified ? "Verified" : "Not verified"}</dd></div><div><dt>Joined</dt><dd>{new Date(user.createdAt).toLocaleDateString()}</dd></div></dl>
      <form onSubmit={event => void save(event)}><label htmlFor="profile-name">Display name</label><input id="profile-name" name="name" className="ws-input" autoComplete="name" value={name} maxLength={80} required onChange={e => setName(e.target.value)} disabled={busy} />
        <button className="pill pill-solid" type="submit" disabled={busy || !name.trim() || name.trim() === user.name}>{busy ? "Saving…" : "Save profile"}</button></form>
      <p role="status" aria-live="polite">{notice}</p>{error && <p role="alert">{error}</p>}
      <button className="pill pill-ghost" disabled={busy} onClick={() => void signOut()}>Sign out</button>
    </dialog>
  </>;
}

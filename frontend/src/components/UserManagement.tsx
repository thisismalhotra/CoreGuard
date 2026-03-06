"use client";

import { useEffect, useState, useCallback } from "react";
import { Users, RefreshCw, ShieldCheck, ShieldOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { api, type UserProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const ROLES = ["admin", "operator", "approver", "viewer"] as const;

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-red-500/15 text-red-400 border-red-500/30",
  operator: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  approver: "bg-purple-500/15 text-purple-400 border-purple-500/30",
  viewer: "bg-muted text-muted-foreground border-border",
};

export function UserManagement() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getUsers();
      setUsers(data);
    } catch {
      toast.error("Failed to load users");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  async function handleRoleChange(userId: number, newRole: string) {
    setUpdatingId(userId);
    try {
      const updated = await api.updateUserRole(userId, newRole);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      toast.success(`Role updated to ${newRole}`);
    } catch {
      toast.error("Failed to update role");
    } finally {
      setUpdatingId(null);
    }
  }

  async function handleToggleActive(userId: number, currentlyActive: boolean) {
    // Safety: admin cannot deactivate themselves
    if (userId === currentUser?.id && currentlyActive) {
      toast.error("You cannot deactivate your own account");
      return;
    }
    setUpdatingId(userId);
    try {
      const updated = await api.updateUserActive(userId, !currentlyActive);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      toast.success(updated.is_active ? "User activated" : "User deactivated");
    } catch {
      toast.error("Failed to update user status");
    } finally {
      setUpdatingId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
        Loading users...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">{users.length} user{users.length !== 1 ? "s" : ""}</span>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 text-xs"
          onClick={fetchUsers}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 border-b border-border">
            <tr>
              <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">User</th>
              <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Email</th>
              <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Role</th>
              <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Status</th>
              <th className="text-right px-4 py-2.5 font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {users.map((u) => {
              const isSelf = u.id === currentUser?.id;
              const isUpdating = updatingId === u.id;
              return (
                <tr key={u.id} className={`transition-colors ${!u.is_active ? "opacity-50" : "hover:bg-muted/30"}`}>
                  {/* User */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      {u.picture ? (
                        <img
                          src={u.picture}
                          alt={u.name}
                          className="h-7 w-7 rounded-full shrink-0"
                          referrerPolicy="no-referrer"
                        />
                      ) : (
                        <div className="h-7 w-7 rounded-full bg-muted flex items-center justify-center text-xs font-medium shrink-0">
                          {u.name.charAt(0).toUpperCase()}
                        </div>
                      )}
                      <div>
                        <span className="font-medium">{u.name}</span>
                        {isSelf && (
                          <span className="ml-1.5 text-[10px] text-muted-foreground">(you)</span>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* Email */}
                  <td className="px-4 py-3 text-muted-foreground">{u.email}</td>

                  {/* Role */}
                  <td className="px-4 py-3">
                    <select
                      value={u.role}
                      disabled={isUpdating}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      className={`text-xs font-medium px-2 py-1 rounded border bg-transparent cursor-pointer
                        disabled:cursor-not-allowed disabled:opacity-50
                        focus:outline-none focus:ring-1 focus:ring-ring
                        ${ROLE_COLORS[u.role] ?? ROLE_COLORS.viewer}`}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r} className="bg-background text-foreground">
                          {r}
                        </option>
                      ))}
                    </select>
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3">
                    <Badge
                      variant="outline"
                      className={u.is_active
                        ? "border-green-500/30 text-green-400 bg-green-500/10"
                        : "border-border text-muted-foreground"}
                    >
                      {u.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </td>

                  {/* Toggle active */}
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={isUpdating || (isSelf && u.is_active)}
                      onClick={() => handleToggleActive(u.id, u.is_active)}
                      className={`h-7 gap-1 text-xs ${
                        u.is_active
                          ? "text-red-400 hover:text-red-300 hover:bg-red-950/40"
                          : "text-green-400 hover:text-green-300 hover:bg-green-950/40"
                      }`}
                      title={isSelf && u.is_active ? "Cannot deactivate your own account" : undefined}
                    >
                      {u.is_active ? (
                        <><ShieldOff className="h-3.5 w-3.5" />Deactivate</>
                      ) : (
                        <><ShieldCheck className="h-3.5 w-3.5" />Activate</>
                      )}
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

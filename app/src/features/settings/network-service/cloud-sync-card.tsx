import { isTauri } from '@tauri-apps/api/core'
import { RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { SettingsCard } from '@/features/settings/shell/settings-card'
import { nativeCall } from '@/lib/player'

interface CloudSyncConfig {
  serverUrl: string
  token: string
  autoSync: boolean
  lastSyncTime: number | null
}

interface CloudSyncResult {
  success: boolean
  pulled: number
  pushed: number
  timestamp: number
  error?: string | null
}

const DEFAULT_SERVER = ''

export function CloudSyncCard() {
  const [config, setConfig] = useState<CloudSyncConfig>({
    serverUrl: DEFAULT_SERVER,
    token: '',
    autoSync: true,
    lastSyncTime: null
  })
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState<string>()
  const [isError, setIsError] = useState(false)

  const loadConfig = useCallback(async () => {
    if (!isTauri()) return
    try {
      const cfg = await nativeCall<CloudSyncConfig>('cloud_sync_config')
      setConfig(cfg)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    void loadConfig()
  }, [loadConfig])

  const saveConfig = async (patch: Partial<CloudSyncConfig>) => {
    const next = { ...config, ...patch }
    setConfig(next)
    if (isTauri()) {
      try {
        await nativeCall('set_cloud_sync_config', { config: next })
      } catch (e) {
        console.error('Failed to save cloud sync config:', e)
      }
    }
  }

  const handleSync = async () => {
    if (syncing || !isTauri()) return
    setSyncing(true)
    setSyncMsg('正在同步中…')
    setIsError(false)
    try {
      const res = await nativeCall<CloudSyncResult>('cloud_sync')
      if (res.success) {
        setIsError(false)
        setSyncMsg(`同步完成！已向云端推送 ${res.pushed} 个歌单，拉取 ${res.pulled} 个歌单`)
        setConfig((prev) => ({ ...prev, lastSyncTime: res.timestamp }))
      } else {
        setIsError(true)
        setSyncMsg(res.error || '同步失败')
      }
    } catch (e: any) {
      setIsError(true)
      setSyncMsg(String(e?.message || e))
    } finally {
      setSyncing(false)
    }
  }

  const formatLastSync = (ts: number | null) => {
    if (!ts) return '尚未同步'
    const d = new Date(ts * 1000)
    return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }

  return (
    <section aria-labelledby="cloud-sync-heading" className="flex flex-col gap-6">
      <div>
        <h3 id="cloud-sync-heading" className="text-base font-semibold">
          路由器自建云端同步 (Cloud Sync)
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          将本地歌单（包括 B 站独占二创歌曲、网易云等全平台曲目）同步到路由器，实现 PC 与手机多端无损互通。
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <SettingsCard
          searchId="cloud-sync-server"
          title="同步服务器地址"
          description="部署在路由器上的歌单同步服务 URL。"
        >
          <div className="flex w-full max-w-sm gap-2">
            <Input
              type="url"
              value={config.serverUrl}
              placeholder={DEFAULT_SERVER}
              onChange={(e) => void saveConfig({ serverUrl: e.target.value })}
              className="text-xs"
            />
          </div>
        </SettingsCard>

        <SettingsCard
          searchId="cloud-sync-token"
          title="认证 Token（可选）"
          description="若路由器服务端配置了密码保护，在此填写一致的 Token。"
        >
          <div className="flex w-full max-w-sm gap-2">
            <Input
              type="password"
              value={config.token}
              placeholder="无密码可留空"
              onChange={(e) => void saveConfig({ token: e.target.value })}
              className="text-xs"
            />
          </div>
        </SettingsCard>

        <SettingsCard
          searchId="cloud-sync-auto"
          title="启动时自动同步"
          description="应用启动后自动在后台与路由器同步最新歌单数据。"
        >
          <Switch
            checked={config.autoSync}
            onCheckedChange={(checked) => void saveConfig({ autoSync: checked })}
          />
        </SettingsCard>

        <div className="rounded-lg bg-muted/40 p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <span className="text-xs text-muted-foreground">
                上次同步状态：{formatLastSync(config.lastSyncTime)}
              </span>
              {syncMsg && (
                <span
                  className={`mt-1 text-xs font-medium ${
                    isError ? 'text-destructive' : 'text-primary'
                  }`}
                >
                  {syncMsg}
                </span>
              )}
            </div>

            <Button
              size="sm"
              variant="default"
              disabled={syncing}
              onClick={() => void handleSync()}
              className="gap-2"
            >
              <RefreshCw className={`size-3.5 ${syncing ? 'animate-spin' : ''}`} />
              {syncing ? '正在同步…' : '立即双向同步'}
            </Button>
          </div>
        </div>
      </div>
    </section>
  )
}

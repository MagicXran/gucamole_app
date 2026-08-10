using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace NercarPortal
{
    internal static class PortalFreeCADLauncher
    {
        private const string TargetPath = @"\\tsclient\用户空间";
        private const string DriveName = "U:";
        private const string WorkingDirectory = @"U:\";
        private const string FreeCADPath = @"C:\Program Files\FreeCAD 1.1\bin\freecad.exe";
        private const string FreeCADCmdPath = @"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe";
        private const int WaitSeconds = 60;
        private const int ResourceTypeDisk = 1;
        private const int NoError = 0;
        private const int ErrorMoreData = 234;
        private const int ErrorNotConnected = 2250;
        private static bool mappingCreated;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct NetResource
        {
            public int Scope;
            public int Type;
            public int DisplayType;
            public int Usage;
            public string LocalName;
            public string RemoteName;
            public string Comment;
            public string Provider;
        }

        [DllImport("mpr.dll", CharSet = CharSet.Unicode)]
        private static extern int WNetAddConnection2(
            ref NetResource netResource,
            string password,
            string username,
            int flags);

        [DllImport("mpr.dll", CharSet = CharSet.Unicode)]
        private static extern int WNetCancelConnection2(
            string name,
            int flags,
            bool force);

        [DllImport("mpr.dll", CharSet = CharSet.Unicode)]
        private static extern int WNetGetConnection(
            string localName,
            StringBuilder remoteName,
            ref int length);

        [STAThread]
        private static int Main(string[] args)
        {
            if (args.Length != 0)
            {
                WriteLog("rejected_args", "count=" + args.Length);
                return 2;
            }

            try
            {
                WriteLog("start", string.Empty);
                if (!WaitForTarget())
                {
                    WriteLog("target_unavailable", TargetPath);
                    return 3;
                }

                PrepareMapping();
                SetFreeCADOpenSavePath();

                ProcessStartInfo startInfo = new ProcessStartInfo
                {
                    FileName = FreeCADPath,
                    WorkingDirectory = @"U:\",
                    UseShellExecute = false
                };
                Process process = Process.Start(startInfo);
                if (process == null)
                {
                    throw new InvalidOperationException("FreeCAD process was not created.");
                }

                WriteLog("child_started", "pid=" + process.Id);
                process.WaitForExit();
                WriteLog("child_exited", "exit_code=" + process.ExitCode);
                return process.ExitCode;
            }
            catch (Exception exception)
            {
                WriteLog("failed", exception.GetType().Name + ": " + exception.Message);
                return 1;
            }
            finally
            {
                CleanupMapping();
            }
        }

        private static bool WaitForTarget()
        {
            for (int attempt = 0; attempt < WaitSeconds; attempt++)
            {
                if (Directory.Exists(TargetPath))
                {
                    return true;
                }
                Thread.Sleep(1000);
            }
            return false;
        }

        private static void MapUserSpace()
        {
            NetResource resource = new NetResource
            {
                Type = ResourceTypeDisk,
                LocalName = DriveName,
                RemoteName = TargetPath
            };
            int result = WNetAddConnection2(ref resource, null, null, 0);
            if (result != NoError)
            {
                throw new InvalidOperationException("WNetAddConnection2 failed with code " + result + ".");
            }
            mappingCreated = true;
            if (!Directory.Exists(WorkingDirectory))
            {
                throw new DirectoryNotFoundException("Mapped user-space drive is unavailable.");
            }
            WriteLog("mapped", DriveName + " -> " + TargetPath);
        }

        private static void PrepareMapping()
        {
            string existingTarget = GetMappedTarget();
            if (existingTarget != null)
            {
                if (!string.Equals(existingTarget, TargetPath, StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException(
                        "U: is already mapped to another target: " + existingTarget);
                }
                if (!Directory.Exists(WorkingDirectory))
                {
                    throw new DirectoryNotFoundException("Existing user-space drive is unavailable.");
                }
                WriteLog("mapping_reused", DriveName + " -> " + TargetPath);
                return;
            }
            MapUserSpace();
        }

        private static string GetMappedTarget()
        {
            int length = 512;
            StringBuilder remoteName = new StringBuilder(length);
            int result = WNetGetConnection(DriveName, remoteName, ref length);
            if (result == ErrorNotConnected)
            {
                return null;
            }
            if (result == ErrorMoreData)
            {
                remoteName = new StringBuilder(length);
                result = WNetGetConnection(DriveName, remoteName, ref length);
            }
            if (result != NoError)
            {
                throw new InvalidOperationException("WNetGetConnection failed with code " + result + ".");
            }
            return remoteName.ToString();
        }

        private static void CleanupMapping()
        {
            if (!mappingCreated)
            {
                return;
            }
            int result = WNetCancelConnection2(DriveName, 0, true);
            mappingCreated = false;
            if (result != NoError && result != ErrorNotConnected)
            {
                WriteLog("mapping_cleanup_failed", "code=" + result);
            }
        }

        private static void SetFreeCADOpenSavePath()
        {
            if (!File.Exists(FreeCADCmdPath))
            {
                throw new FileNotFoundException("FreeCADCmd was not found.", FreeCADCmdPath);
            }

            string root = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "NercarPortal");
            Directory.CreateDirectory(root);
            string scriptPath = Path.Combine(root, "set-freecad-open-save-path.py");
            const string source =
                "import FreeCAD\n" +
                "FreeCAD.ParamGet('User parameter:BaseApp/Preferences/General').SetString('FileOpenSavePath', 'U:/')\n" +
                "FreeCAD.ParamGet('User parameter:BaseApp/Preferences/Dialog').SetBool('DontUseNativeDialog', True)\n";
            File.WriteAllText(scriptPath, source, new System.Text.UTF8Encoding(false));

            try
            {
                ProcessStartInfo startInfo = new ProcessStartInfo
                {
                    FileName = FreeCADCmdPath,
                    Arguments = QuoteArgument(scriptPath),
                    WorkingDirectory = WorkingDirectory,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                Process process = Process.Start(startInfo);
                if (process == null)
                {
                    throw new InvalidOperationException("FreeCADCmd process was not created.");
                }
                process.WaitForExit();
                if (process.ExitCode != 0)
                {
                    throw new InvalidOperationException("FreeCADCmd failed with code " + process.ExitCode + ".");
                }
                WriteLog("freecad_path_set", "U:/");
            }
            finally
            {
                if (File.Exists(scriptPath))
                {
                    File.Delete(scriptPath);
                }
            }
        }

        private static string QuoteArgument(string value)
        {
            return "\"" + value.Replace("\"", "\\\"") + "\"";
        }

        private static void WriteLog(string stage, string detail)
        {
            try
            {
                string root = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "NercarPortal");
                Directory.CreateDirectory(root);
                string path = Path.Combine(root, "portal-freecad-launcher.log");
                int sessionId = Process.GetCurrentProcess().SessionId;
                string safeDetail = (detail ?? string.Empty).Replace('\r', ' ').Replace('\n', ' ');
                string line = string.Format(
                    "{0:o} session={1} stage={2} detail={3}{4}",
                    DateTimeOffset.Now,
                    sessionId,
                    stage,
                    safeDetail,
                    Environment.NewLine);
                File.AppendAllText(path, line, new System.Text.UTF8Encoding(false));
            }
            catch
            {
                // 日志失败不覆盖 Launcher 的原始退出结果。
            }
        }
    }
}

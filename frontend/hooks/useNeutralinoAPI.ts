// frontend/hooks/useNeutralinoAPI.ts
import { useEffect, useState } from 'react';

// Declare Neutralino globally for TypeScript, only if not already declared elsewhere in project
// This is often done in a global .d.ts file, but for a self-contained hook:
declare global {
  interface Window {
    Neutralino: any; // Use 'any' for simplicity or define specific Neutralino types
    NL_NEUTRINO_APP?: boolean; // Flag to check if running inside Neutralino
    NL_APP_DATA_PATH?: string; // Injected by the Neutralinojs shell
  }
}

export interface NeutralinoFileOpenDialogOptions {
    multiSelections?: boolean;
    filters?: Array<{ name: string; extensions: string[] }>;
}

export interface NeutralinoFileSaveDialogOptions {
    forceOverwrite?: boolean;
}


export interface NeutralinoAPI {
  isNeutralinoAvailable: boolean;
  os: {
    showOpenDialog: (title: string, options?: NeutralinoFileOpenDialogOptions) => Promise<string[] | string>;
    showSaveDialog: (title: string, options?: NeutralinoFileSaveDialogOptions) => Promise<string>;
    showNotification: (title: string, content: string, icon?: 'INFO' | 'WARNING' | 'ERROR' | 'QUESTION') => Promise<void>;
  };
  filesystem: {
    getPath: (name: 'appData' | 'data' | 'documents' | 'downloads' | 'cache' | 'exe' | 'currentWorkDir' | 'config' | 'logs' | 'temp' | 'extensions' | 'resource') => Promise<string>;
    createDirectory: (path: string) => Promise<void>;
    readFile: (path: string) => Promise<string>;
    readBinaryFile: (path: string) => Promise<ArrayBuffer>;
    // Add other filesystem functions as needed
  };
  // Add other Neutralino modules as needed (window, app, storage, extensions etc.)
  extensions: {
    spawnProcess: (command: string) => Promise<{ id: number; pid: number; stdOut?: string; stdErr?: string; exitCode?: number; }>; // Simplified, actual might vary
    // Add other extension functions as needed
  };
  app: {
    exit: (exitCode?: number) => Promise<void>;
  };
  events: {
    on: (eventName: string, handler: (event?: any) => void) => Promise<void>;
    // Add other event functions as needed
  };
}

const useNeutralinoAPI = (): NeutralinoAPI => {
  const [isAvailable, setIsAvailable] = useState(false);

  useEffect(() => {
    // Check if Neutralino global object exists and key APIs are present
    if (typeof window.Neutralino !== 'undefined' &&
        window.Neutralino.os &&
        window.Neutralino.filesystem &&
        window.Neutralino.extensions && // Check for extensions module
        window.Neutralino.app && // Check for app module
        window.Neutralino.events // Check for events module
        ) {
      setIsAvailable(true);
      window.NL_NEUTRINO_APP = true; // Set a global flag
    } else {
      setIsAvailable(false);
      window.NL_NEUTRINO_APP = false;
    }
  }, []);

  // Define the API object structure with typed functions
  const neutralinoAPI: NeutralinoAPI = {
    isNeutralinoAvailable: isAvailable,
    os: {
      showOpenDialog: async (title, options = {}) => {
        if (isAvailable) {
          try {
            const result = await window.Neutralino.os.showOpenDialog(title, options);
            return result;
          } catch (err) {
            console.error("Neutralino.os.showOpenDialog error:", err);
            throw err;
          }
        }
        console.warn('Neutralino API not available: showOpenDialog called.');
        throw new Error('Neutralino API not available for showOpenDialog');
      },
      showSaveDialog: async (title, options = {}) => {
        if (isAvailable) {
          try {
            return await window.Neutralino.os.showSaveDialog(title, options);
          } catch (err) {
            console.error("Neutralino.os.showSaveDialog error:", err);
            throw err;
          }
        }
        console.warn('Neutralino API not available: showSaveDialog called.');
        throw new Error('Neutralino API not available for showSaveDialog');
      },
      showNotification: async (title, content, icon = 'INFO') => {
        if (isAvailable) {
          try {
            await window.Neutralino.os.showNotification(title, content, icon);
          } catch (err) {
            console.error("Neutralino.os.showNotification error:", err);
            // For notifications, might not re-throw, just log.
          }
        } else {
          console.warn(`Neutralino API not available: showNotification called with title "${title}", content "${content}"`);
          // Fallback: could use browser notification API or a toast library.
          // For this hook, we just log if Neutralino is not there.
        }
      },
    },
    filesystem: {
      getPath: async (name) => {
        if (isAvailable) {
          try {
            return await window.Neutralino.filesystem.getPath(name);
          } catch (err) {
            console.error(`Neutralino.filesystem.getPath('${name}') error:`, err);
            throw err;
          }
        }
        console.warn(`Neutralino API not available: getPath('${name}') called.`);
        // Fallback for 'data' path if injected by shell, useful for web development mode
        if (name === 'data' && window.NL_APP_DATA_PATH) {
            console.log("Using injected NL_APP_DATA_PATH as fallback for getPath('data').");
            return window.NL_APP_DATA_PATH;
        }
        throw new Error(`Neutralino API not available for getPath('${name}')`);
      },
      createDirectory: async (path: string) => {
        if (isAvailable) {
            try {
                return await window.Neutralino.filesystem.createDirectory(path);
            } catch (err) {
                console.error(`Neutralino.filesystem.createDirectory('${path}') error:`, err);
                throw err;
            }
        }
        console.warn(`Neutralino API not available: createDirectory('${path}') called.`);
        throw new Error(`Neutralino API not available for createDirectory('${path}')`);
      },
      readFile: async (path: string) => {
        if (isAvailable) {
            try {
                return await window.Neutralino.filesystem.readFile(path);
            } catch (err) {
                console.error(`Neutralino.filesystem.readFile('${path}') error:`, err);
                throw err;
            }
        }
        console.warn(`Neutralino API not available: readFile('${path}') called.`);
        throw new Error(`Neutralino API not available for readFile('${path}')`);
      },
      readBinaryFile: async (path: string) => {
        if (isAvailable) {
            try {
                return await window.Neutralino.filesystem.readBinaryFile(path);
            } catch (err) {
                console.error(`Neutralino.filesystem.readBinaryFile('${path}') error:`, err);
                throw err;
            }
        }
        console.warn(`Neutralino API not available: readBinaryFile('${path}') called.`);
        throw new Error(`Neutralino API not available for readBinaryFile('${path}')`);
      }
    },
    extensions: {
        spawnProcess: async (command: string) => {
            if(isAvailable) {
                try {
                    return await window.Neutralino.extensions.spawnProcess(command);
                } catch (err) {
                    console.error(`Neutralino.extensions.spawnProcess error with command "${command}":`, err);
                    throw err;
                }
            }
            console.warn(`Neutralino API not available: spawnProcess called with command "${command}".`);
            throw new Error('Neutralino API not available for spawnProcess');
        }
    },
    app: {
        exit: async (exitCode = 0) => {
            if(isAvailable) {
                try {
                    await window.Neutralino.app.exit(exitCode);
                } catch (err) {
                    console.error(`Neutralino.app.exit error:`, err);
                    // If Neutralino exit fails, try a standard window close as last resort
                    // This might not always work as expected for cleanup.
                    window.close();
                }
            } else {
                console.warn('Neutralino API not available: app.exit called.');
                window.close(); // Fallback for web environment
            }
        }
    },
    events: {
        on: async (eventName: string, handler: (event?: any) => void) => {
            if(isAvailable) {
                try {
                    return await window.Neutralino.events.on(eventName, handler);
                } catch (err) {
                    console.error(`Neutralino.events.on('${eventName}') error:`, err);
                    throw err;
                }
            }
            console.warn(`Neutralino API not available: events.on('${eventName}') called.`);
            // No easy fallback for events in browser unless you implement a mock event system.
            throw new Error(`Neutralino API not available for events.on('${eventName}')`);
        }
    }
  };

  return neutralinoAPI;
};

export default useNeutralinoAPI;

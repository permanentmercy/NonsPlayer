use std::{fs, path::Path};

struct AdapterResource {
    name: &'static str,
    manifest: &'static [u8],
    wasm: &'static [u8],
    licenses: &'static [(&'static str, &'static [u8])],
}

const ADAPTERS: &[AdapterResource] = &[
    AdapterResource {
        name: "bilibili",
        manifest: include_bytes!("../../../bundled-adapters/bilibili/manifest.json"),
        wasm: include_bytes!("../../../bundled-adapters/bilibili/adapter.component.wasm"),
        licenses: &[
            (
                "License",
                include_bytes!("../../../bundled-adapters/bilibili/License"),
            ),
        ],
    },
];

pub(crate) fn materialize(root: &Path) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    for adapter in ADAPTERS {
        let directory = root.join(adapter.name);
        fs::create_dir_all(&directory)?;
        fs::write(directory.join("manifest.json"), adapter.manifest)?;
        fs::write(directory.join("adapter.component.wasm"), adapter.wasm)?;
        for (name, contents) in adapter.licenses {
            fs::write(directory.join(name), contents)?;
        }
    }
    Ok(())
}

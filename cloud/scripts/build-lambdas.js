const { execSync } = require('child_process');
const { readdirSync, existsSync } = require('fs');
const { join } = require('path');

const LAMBDA_DIR = 'lib/assets/lambdas';

// Get all subdirectories in LAMBDA_DIR
const directories = readdirSync(LAMBDA_DIR, { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .map(dirent => join(LAMBDA_DIR, dirent.name));

// Run npm install if package.json exists
directories.forEach(dir => {
    const packageJsonPath = join(dir, 'package.json');
    if (existsSync(packageJsonPath)) {
        console.log(`Running npm install in ${dir}`);
        execSync('npm install', { cwd: dir, stdio: 'inherit' });
    }
});

console.log('Finished installing npm packages.');
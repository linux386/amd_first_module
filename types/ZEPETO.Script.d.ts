declare module 'ZEPETO.Script' {
    export class ZepetoScriptBehaviour {
        transform: Transform;
        Start(): void;
        Update(): void;
    }
}

interface Transform {
    position: Vector3;
    forward: Vector3;
    Rotate(x: number, y: number, z: number): void;
    Translate(vector: Vector3): void;
}

interface Vector3 {
    x: number;
    y: number;
    z: number;
    normalized: Vector3;
} 
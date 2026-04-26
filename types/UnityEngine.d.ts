declare module 'UnityEngine' {
    export class Time {
        static time: number;
        static deltaTime: number;
    }

    export class Random {
        static RangeFloat(min: number, max: number): number;
    }

    export class Vector3 {
        x: number;
        y: number;
        z: number;
        constructor(x: number, y: number, z: number);
    }
} 
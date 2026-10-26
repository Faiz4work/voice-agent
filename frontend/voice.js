import VapiModule from '@vapi-ai/web';
// The published SDK uses CommonJS default exports; normalize its browser bundle.
const Vapi = typeof VapiModule === 'function' ? VapiModule : VapiModule.default;
export default Vapi;
